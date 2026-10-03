// pedal_relay.cs include in H1S4 SW Left -- S167 host <-> P1 pedal relay
//
// The pedal hangs off USART2: PA2 (pin 16, P44, PDL_TX) -> U36 -> J8, and
// J8 -> U37 -> PA3 (pin 17, P45, PDL_RX). Up to S139 the pedal's replies were
// never read. This file lets the host talk to the pedal through MH1 with
// ordinary bus lines that start "/%". Every panel MCU treats a '/'-led line
// as an ignored comment (IgnOn), so nothing else on the bus acts on them, and
// MH1 forwards them like any other line in both directions.
//
// Host -> H1S4 (one command per line, uppercase):
//   /%O<p>[baud]   open the relay: p = 'N' 8N1 (P1 app) or 'E' 8E1 (ROM
//                  bootloader); baud in decimal, 1200..115200, default 115200
//   /%T<hex>       send these bytes to the pedal (at most 48 per line)
//   /%X            close: USART2 back to 115200 8N1, blink forwarding resumes
//   /%I            identity and counters
// H1S4 -> host (lowercase, so H1S4 does not take its own S2S echo for a command):
//   /%o<p><baud> H1S4-PDL1    /%x    /%i ...    /%e <reason>
//   /%r<hex>       pedal bytes, flushed after 2 ms idle or 40 bytes
//
// With the relay closed (the power-up state) H1S4 behaves exactly as the S139
// build: ':' and '.' forwarded to the pedal on every blink, pedal bytes dropped.

#include <stdio.h>
#include <stdlib.h>

#define PDL_ID "H1S4-PDL1"
#define PDL_LINE 100                                // MH1 hostMessage/sMessage are 100 bytes
#define PDL_TX_MAX 48                               // "/%T" + 96 hex + '\n' = 100
#define PDL_CHUNK 40                                // "/%r" + 80 hex + '\n' = 84
#define PDL_IDLE_MS 2

static char pdlCap = 0;                             // 1 = capturing a "/%" line
static char pdlCol = 0;                             // chars seen on this bus line (capped at 2)
static char pdlPrev = 0;                            // previous char on this bus line
static char pdlCapBuf[PDL_LINE];
static unsigned char pdlCapLen = 0;
static char pdlCmd[PDL_LINE];
static volatile char pdlCmdReady = 0;

static volatile char pdlOpen = 0;
static char pdlParity = 'N';
static unsigned long pdlBaud = 115200;
static volatile unsigned char pdlRing[256];         // unsigned char indices wrap at 256
static volatile unsigned char pdlHead = 0, pdlTail = 0;
static volatile uint32_t pdlLastRx = 0;
static volatile unsigned long pdlRxCount = 0, pdlErrCount = 0, pdlDropCount = 0;
static unsigned long pdlTxCount = 0;

static char pdlRep[PDL_LINE];                       // command reply, sent before data
static volatile char pdlRepReady = 0;
static char pdlOut[PDL_LINE];                       // pedal data line
static volatile char pdlOutReady = 0;

static const char PDL_HEX[] = "0123456789ABCDEF";

// Bus RX hook, called from Uart1_Int for every byte before Rx_Fun.
// Returns 1 when the relay consumed the byte; 0 hands it to Rx_Fun as before.
int PdlBusChar(char c)
{
    if (pdlCap)
    {
        if (c == '\n')
        {
            pdlCap = 0; pdlCol = 0; pdlPrev = 0;
            pdlCapBuf[pdlCapLen] = 0;
            if (pdlCapBuf[0] >= 'A' && pdlCapBuf[0] <= 'Z')
            {
                if (pdlCmdReady) pdlDropCount++;    // previous command not yet taken
                else { memcpy(pdlCmd, pdlCapBuf, pdlCapLen + 1); pdlCmdReady = 1; }
            }
            return 0;                               // Eol runs: the bus handshake is unchanged
        }
        if (pdlCapLen < PDL_LINE - 1) pdlCapBuf[pdlCapLen++] = c;
        return 1;
    }
    if (c == '\n') { pdlCol = 0; pdlPrev = 0; return 0; }
    if (pdlCol == 1 && pdlPrev == '/' && c == '%')
    {
        pdlCap = 1; pdlCapLen = 0;
        return 1;
    }
    pdlPrev = c;
    if (pdlCol < 2) pdlCol++;
    return 0;
}

// USART2 (pedal) RX, called from USART2_IRQHandler before the HAL handler.
void Uart2_Int(void)
{
    if (USART2->ISR & (USART_ISR_PE | USART_ISR_FE | USART_ISR_NE | USART_ISR_ORE)) pdlErrCount++;
    while (USART2->ISR & USART_ISR_RXNE)
    {
        unsigned char b = (unsigned char)(USART2->RDR & 0xFF);
        if (pdlOpen)
        {
            if ((unsigned char)(pdlHead + 1) != pdlTail) { pdlRing[pdlHead] = b; pdlHead++; pdlRxCount++; }
            else pdlDropCount++;
            pdlLastRx = HAL_GetTick();
        }
    }
    USART2->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NCF | USART_ICR_PECF;
}

static void PdlUart(char parity, unsigned long baud)
{
    __HAL_UART_DISABLE_IT(&huart2, UART_IT_RXNE);
    huart2.Init.BaudRate = baud;
    huart2.Init.WordLength = (parity == 'E') ? UART_WORDLENGTH_9B : UART_WORDLENGTH_8B;
    huart2.Init.Parity = (parity == 'E') ? UART_PARITY_EVEN : UART_PARITY_NONE;
    HAL_UART_Init(&huart2);
    (void)USART2->RDR;
    USART2->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NCF | USART_ICR_PECF;
}

static int PdlHexVal(char c)
{
    if (c >= '0' && c <= '9') return c - '0';
    if (c >= 'A' && c <= 'F') return c - 'A' + 10;
    if (c >= 'a' && c <= 'f') return c - 'a' + 10;
    return -1;
}

static void PdlReply(const char *s)
{
    if (pdlRepReady) { pdlDropCount++; return; }
    snprintf(pdlRep, sizeof(pdlRep), "/%%%s\n", s);
    pdlRepReady = 1;
}

static void PdlCommand(const char *cmd)
{
    char buf[80];
    switch (cmd[0])
    {
    case 'O':
    {
        char p = cmd[1];
        unsigned long baud = 115200;
        if (p != 'N' && p != 'E') { PdlReply("e parity"); break; }
        if (cmd[2]) baud = strtoul(cmd + 2, 0, 10);
        if (baud < 1200 || baud > 115200) { PdlReply("e baud"); break; }
        pdlOpen = 0;
        PdlUart(p, baud);
        pdlParity = p; pdlBaud = baud;
        pdlHead = pdlTail = 0;
        pdlOpen = 1;
        __HAL_UART_ENABLE_IT(&huart2, UART_IT_RXNE);
        snprintf(buf, sizeof(buf), "o%c%lu %s", p, baud, PDL_ID);
        PdlReply(buf);
        break;
    }
    case 'X':
        pdlOpen = 0;
        PdlUart('N', 115200);
        pdlParity = 'N'; pdlBaud = 115200;
        pdlHead = pdlTail = 0;
        PdlReply("x");
        break;
    case 'T':
    {
        uint8_t data[PDL_TX_MAX];
        int n = 0, i = 1;
        if (!pdlOpen) { PdlReply("e closed"); break; }
        while (cmd[i] && cmd[i + 1] && n < PDL_TX_MAX)
        {
            int hi = PdlHexVal(cmd[i]), lo = PdlHexVal(cmd[i + 1]);
            if (hi < 0 || lo < 0) { n = -1; break; }
            data[n++] = (uint8_t)(hi << 4 | lo);
            i += 2;
        }
        if (n < 0 || cmd[i]) { PdlReply("e hex"); break; }
        if (n) { HAL_UART_Transmit(&huart2, data, (uint16_t)n, 100); pdlTxCount += n; }
        break;
    }
    case 'I':
        snprintf(buf, sizeof(buf), "i %s open=%d fmt=%c%lu rx=%lu tx=%lu err=%lu drop=%lu",
                 PDL_ID, pdlOpen, pdlParity, pdlBaud, pdlRxCount, pdlTxCount, pdlErrCount, pdlDropCount);
        PdlReply(buf);
        break;
    default:
        PdlReply("e cmd");
        break;
    }
}

// Main-loop service: run a received command, then package pedal bytes.
void PdlService(void)
{
    if (pdlCmdReady)
    {
        PdlCommand(pdlCmd);
        pdlCmdReady = 0;
    }
    if (pdlOpen && !pdlOutReady && pdlHead != pdlTail)
    {
        unsigned char n = (unsigned char)(pdlHead - pdlTail);
        if (n >= PDL_CHUNK || (uint32_t)(HAL_GetTick() - pdlLastRx) >= PDL_IDLE_MS)
        {
            int k = 0;
            if (n > PDL_CHUNK) n = PDL_CHUNK;
            pdlOut[k++] = '/'; pdlOut[k++] = '%'; pdlOut[k++] = 'r';
            while (n--)
            {
                unsigned char b = pdlRing[pdlTail]; pdlTail++;
                pdlOut[k++] = PDL_HEX[b >> 4];
                pdlOut[k++] = PDL_HEX[b & 0x0f];
            }
            pdlOut[k++] = '\n';
            pdlOut[k] = 0;
            pdlOutReady = 1;
        }
    }
}

int PdlWantsBus(void) { return pdlRepReady || pdlOutReady; }

// Called from Poll() when MH1 grants the bus and no test message is due.
// Returns 1 when it used the grant.
int PdlSend(void)
{
    if (pdlRepReady)
    {
        HAL_UART_Transmit(&huart1, (uint8_t*)pdlRep, (uint16_t)strlen(pdlRep), HAL_MAX_DELAY);
        pdlRepReady = 0;
        return 1;
    }
    if (pdlOutReady)
    {
        HAL_UART_Transmit(&huart1, (uint8_t*)pdlOut, (uint16_t)strlen(pdlOut), HAL_MAX_DELAY);
        pdlOutReady = 0;
        return 1;
    }
    return 0;
}
