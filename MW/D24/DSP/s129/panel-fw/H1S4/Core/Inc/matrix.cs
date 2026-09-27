// matrix.cs include in H1S4 SW Left

// include
#include <string.h>
#include "matrix.h"

//#include "c:/dropbox/_mx/MW/D24/MX/mxDef.h"
//#include "c:/dropbox/_mx/MW/D24/MX/skinDef.h"

// matrix start
const unsigned int MATRIX[] = // local matrix cells
{
   0x0, // reserved and unused
   Sys001Enc001,
   Sys001Skin001,
   Sys001Test001,
   Sys001Test002,
};
enum // MATRIX cell pointers
{
   p0, // reserved and unused
   pSys001Enc001,
   pSys001Skin001,
   pSys001Test001,
   pSys001Test002,
   MATRIX_X,
};
struct rSw { GPIO_TypeDef *port; uint16_t pin; int matrixAdd; int radioData; }; // radio switch
struct rSw rsw[] = // radio switch properties
{
    { GPIOC, PC8_Pin, pSys001Skin001, 1 },
    { GPIOA, PA11_Pin, pSys001Skin001, 2 },
    { GPIOF, PF6_Pin, pSys001Skin001, 3 },
    { GPIOA, PA15_Pin, pSys001Skin001, 4 },
    { GPIOB, PB0_Pin, pSys001Skin001, 5 },
    { GPIOB, PB10_Pin, pSys001Skin001, 6 },
};
struct wLed { GPIO_TypeDef *port; uint16_t pin; int matrixAdd; int radioData; }; // radio led
struct wLed wled[] = // radio led properties
{
    { GPIOC, PC7_Pin | PC9_Pin, pSys001Skin001, 1 },
    { GPIOA, PA8_Pin | PA12_Pin, pSys001Skin001, 2 },
    { GPIOA, PA13_Pin, pSys001Skin001, 3 },
    { GPIOF, PF7_Pin, pSys001Skin001, 3 },
    { GPIOA, PA14_Pin, pSys001Skin001, 4 },
    { GPIOC, PC10_Pin, pSys001Skin001, 4 },
    { GPIOB, PB1_Pin, pSys001Skin001, 5 },
    { GPIOC, PC5_Pin, pSys001Skin001, 5 },
    { GPIOB, PB2_Pin | PB11_Pin, pSys001Skin001, 6 },
};
// matrix end

// define 
const char AX[] = { 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o', 'p', 'q', 'r', 's', 't', 'u', 'v', 'w', };
const char DX[] = { '0', '1', '2', '3', '4', '5', '6', '7', '8', '9', 'A', 'B', 'C', 'D', 'E', 'F', };
enum { TXD, TXF, RXD, RXF, MATRIX_Y };              // matrix cell data and flags
unsigned char matrix[MATRIX_X][MATRIX_Y] ;          // matrix cell data and flag array

// variable
char matrixFill = 0;                                // flag to sequentially fill matrix cells
char s_blink = 0;							        // system blink mode, 0 = LED off, 1 = LED on
char s_blink1 = 0;                                  // last activated blink status
char s_help = 0;							        // system help mode, all controls send non-executable values
char ignor = 0;                                     // if = 1 then ignore, for messaging only
char test = 1;								        // test flag
char testMessage[100] = "// H1S4 SW Left\n";        // test message
unsigned int a = 0;							        // matrix address
unsigned char d = 0;						        // matrix data
char encLed = 0;                                    // variable selects encoder led: 0 = off, 1-8 sets radio led
char radioLed = 0;                                  // variable selects sw led: 0 = off, 1-14 sets radio led
char ledFollowSw = 1;                               // 0 = blink mode, 1 = led follows switch
unsigned int TXptr = 1;

// typedef
GPIO_InitTypeDef GPIO_InitStruct = { 0 };           // hal gpio
GPIO_InitTypeDef GPIO_BusyStruct = { 0 };           // hal gpio

// extern
extern char UART1_Read();                           // placed inside hal interupt
extern UART_HandleTypeDef huart1;
extern UART_HandleTypeDef huart2;

void TestMessage(void);
void RdRadioSwitches(void);
void WrRadioLeds(void);
void WrRadioLed(struct wLed s);

// function
void Poll(void) // TX, check if any cell data, or test message is flagged to send
{
    if (test) { HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_RESET); } // if test message is ready, set data ready flag to H mcu
    //if (matrix[iPtr][TXF]) { TXptr = iPtr; HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_RESET); } // set ready flag
    if (matrix[TXptr][TXF]) { HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_RESET); } // set ready flag
    // instead of checking TX/RX flags, check if TXD and RXD are different?
    //if (matrix[iPtr][TXD] != matrix[iPtr][RXD]) { TXptr = iPtr; HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_RESET); } // set ready flag
    // note reasons to use TXF and RXF:
    // TXD and TXF are local flags, and confirm that data has been successfully sent and received, and executed
    // TXD and RXF can be applied to sequential cell groups, for efficiency, e.g. strings, or atomic data
    //else { iPtr++; if (iPtr == MATRIX_X) iPtr = 1; } // inc pointer to check next control
    else { TXptr++; if (TXptr == MATRIX_X) TXptr = 1; } // inc pointer to check next control
    if (HAL_GPIO_ReadPin(S3_GPIO_Port, S3_Pin)) // check MH MCU data request
    {
        if (test) { TestMessage(); } // send test message
        else // send matrix cell data
        {
            int dataLen = 0;
            uint8_t data[10];
            if (MATRIX[TXptr] & 0xf000) { data[dataLen] = AX[MATRIX[TXptr] >> 12 & 0x0f]; dataLen++; }      // write A ms nibble
            if (MATRIX[TXptr] & 0xff00) { data[dataLen] = AX[MATRIX[TXptr] >> 8 & 0x0f]; dataLen++; }
            if (MATRIX[TXptr] & 0xfff0) { data[dataLen] = AX[MATRIX[TXptr] >> 4 & 0x0f]; dataLen++; }
            if (MATRIX[TXptr] & 0xffff) { data[dataLen] = AX[MATRIX[TXptr] & 0x0f]; dataLen++; }            // write A ls nibble
            if (matrix[TXptr][TXD] & 0xf0) { data[dataLen] = DX[matrix[TXptr][TXD] >> 4]; dataLen++; }      // write D ms nibble
            if (matrix[TXptr][TXD] & 0xff) { data[dataLen] = DX[matrix[TXptr][TXD] & 0x0f]; dataLen++; }    // write D ls nibble
            data[dataLen] = '\n'; dataLen++;
            HAL_UART_Transmit(&huart1, data, dataLen, HAL_MAX_DELAY);
            if (matrix[TXptr][TXF]) matrix[TXptr][TXF]--;
        }
        while (HAL_GPIO_ReadPin(S3_GPIO_Port, S3_Pin)) 
        {
            //GPIO_InitStruct.Pin = PB2_Pin | PB11_Pin;
            //GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
            //HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
            //HAL_GPIO_WritePin(GPIOB, PB2_Pin | PB11_Pin, GPIO_PIN_SET);
        } // wait for MH MCU data request reset to avoid bus contention
        GPIO_InitStruct.Pin = PB2_Pin | PB11_Pin;
        GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
        HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
    }
}

void MainInit()
{
    // init matrix bus
    GPIO_InitStruct.Pin = S2_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    HAL_GPIO_Init(S2_GPIO_Port, &GPIO_InitStruct);
    HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_SET); // data ready handshake pin
    // init uart interrupt busy pin
    GPIO_BusyStruct.Pin = BUSY_Pin;

    // init LEDs
    /*
        GPIO_InitStruct.Pin = PA8_Pin | PA12_Pin | PA13_Pin | PA14_Pin;
        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);
        GPIO_InitStruct.Pin = PB1_Pin | PB2_Pin | PB11_Pin;
        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
        HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);
        GPIO_InitStruct.Pin = PC5_Pin | PC7_Pin | PC9_Pin | PC10_Pin;
        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
        HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);
        GPIO_InitStruct.Pin = PF7_Pin;
        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
        HAL_GPIO_Init(GPIOF, &GPIO_InitStruct);
    */
}

void MainLoop()
{
    RdRadioSwitches();
    //    if (ledFollowSw)
    //    {
    WrRadioLeds();
    //    }
    //    else
    //    {
    if (s_blink != s_blink1)
    {
        if (s_blink)
        {
            // blink on routines here...
            /*    
            HAL_GPIO_WritePin(GPIOA, PA8_Pin | PA12_Pin | PA13_Pin | PA14_Pin, GPIO_PIN_SET);
                HAL_GPIO_WritePin(GPIOB, PB1_Pin | PB2_Pin | PB11_Pin, GPIO_PIN_SET);
                HAL_GPIO_WritePin(GPIOC, PC5_Pin | PC7_Pin | PC9_Pin | PC10_Pin, GPIO_PIN_SET);
                HAL_GPIO_WritePin(GPIOF, PF7_Pin, GPIO_PIN_SET);
            */
            // TX ':' to UART2
            int dataLen = 0;
            uint8_t data[2];
            data[dataLen] = ':'; dataLen++;
            data[dataLen] = '\n'; dataLen++;
            HAL_UART_Transmit(&huart2, data, dataLen, HAL_MAX_DELAY);
        }
        else
        {
            // blink off routines here...
            /*    
            HAL_GPIO_WritePin(GPIOA, PA8_Pin | PA12_Pin | PA13_Pin | PA14_Pin, GPIO_PIN_RESET);
                HAL_GPIO_WritePin(GPIOB, PB1_Pin | PB2_Pin | PB11_Pin, GPIO_PIN_RESET);
                HAL_GPIO_WritePin(GPIOC, PC5_Pin | PC7_Pin | PC9_Pin | PC10_Pin, GPIO_PIN_RESET);
                HAL_GPIO_WritePin(GPIOF, PF7_Pin, GPIO_PIN_RESET);
            */
            // TX '.' to UART2
            int dataLen = 0;
            uint8_t data[2];
            data[dataLen] = '.'; dataLen++;
            data[dataLen] = '\n'; dataLen++;
            HAL_UART_Transmit(&huart2, data, dataLen, HAL_MAX_DELAY);
        }
        s_blink1 = s_blink;
    }
    Poll();
}

void RdRadioSwitch(struct rSw s)
{
    if (!HAL_GPIO_ReadPin(s.port, s.pin) && matrix[s.matrixAdd][TXD] != s.radioData)
    {
        ledFollowSw = 1; matrix[s.matrixAdd][TXD] = s.radioData;
        if (matrix[s.matrixAdd][TXF] < 2) matrix[s.matrixAdd][TXF]++;
    }
}

void RdRadioSwitches()
    {
    for (int i = 0; i < sizeof(rsw) / sizeof(rsw[0]); i++)
    {
        RdRadioSwitch(rsw[i]);
    }
}
void WrRadioLeds()
{
    for (int i = 0; i < sizeof(wled) / sizeof(wled[0]); i++)
    {
        WrRadioLed(wled[i]);
    }
}

void WrRadioLed(struct wLed s)
{
    if (matrix[s.matrixAdd][RXD] == s.radioData) 
    {
        //HAL_GPIO_WritePin(s.port, s.pin, GPIO_PIN_SET);
        // convert to output for bright led
        GPIO_InitStruct.Pin = s.pin;
        GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
        HAL_GPIO_Init(s.port, &GPIO_InitStruct);
        HAL_GPIO_WritePin(s.port, s.pin, GPIO_PIN_SET);
    }
    else
    {
        //HAL_GPIO_WritePin(s.port, s.pin, GPIO_PIN_RESET);
        // convert to input for dim led
        GPIO_InitStruct.Pin = s.pin;
        GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
        HAL_GPIO_Init(s.port, &GPIO_InitStruct);
    }
}

// matrix function
void Spare(void) { }
void Meter(void) { }                        // legacy allocation to control meter ballistics, instead of dsp control
void MfOn(void) { matrixFill = 1; }         // start matrix fill mode
void MfOf(void) { }                         // stop matrix fill mode
void BlkOn(void)                            // blink on
{ 
    s_blink = 1;
}
void BlkOf(void)                            // blink off 
{ 
    s_blink = 0;
}
void Tick(void) { }                         // unused legacy tick counter
void HlpOn(void) { s_help = 1; }            // help mode on, no data loaded to cells during this mode
void HlpOf(void) { s_help = 0; }            // hrlp mode off
void IgnOn(void) { ignor = 1; }             // ignore data characters, for system comment logs only (prefixed with "//"
void Test(void) { test = 1; }               // send mcu test message to host if true
void TestMessage(void)                      // send mcu test message to host
{
    HAL_UART_Transmit(&huart1, (uint8_t*)testMessage, (uint16_t)strlen(testMessage), HAL_MAX_DELAY);
    test = 0;
}

void Eol(void) // RX, end-of-line, bus matrix message received
{
    //GPIO_BusyStruct.Pin = BUSY_Pin;
    GPIO_BusyStruct.Mode = GPIO_MODE_OUTPUT_PP;
    HAL_GPIO_Init(BUSY_GPIO_Port, &GPIO_BusyStruct);
    HAL_GPIO_WritePin(BUSY_GPIO_Port, BUSY_Pin, GPIO_PIN_RESET); // mcu/bus is busy
    if ((!s_help) && (!ignor)) 
    { 
        for (int i = 1; i < MATRIX_X; i++) // find local matrix address
        {
            if (a == MATRIX[i]) // local matrix address found
            {
                matrix[i][RXD] = d; // write local matrix data
                if (matrix[i][RXF] < 2) matrix[i][RXF]++;
                break;
            }
        }
    }
    d = 0;                  // reset local data value
    ignor = 0;              // reset ignore comment flag
    if (matrixFill) a++;    // inc matrix fill address
    else a = 0;             // reset local address value
    HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_SET);  // message decoded and data stored, handshake with H mcu
    //GPIO_BusyStruct.Pin = BUSY_Pin;
    GPIO_BusyStruct.Mode = GPIO_MODE_INPUT;
    HAL_GPIO_Init(BUSY_GPIO_Port, &GPIO_BusyStruct);        // mcu/bus is not busy
}

// matrix bus message, address and data translator
void A_00(void) { a <<= 4; a += 0x00; } void A_01(void) { a <<= 4; a += 0x01; }
void A_02(void) { a <<= 4; a += 0x02; } void A_03(void) { a <<= 4; a += 0x03; }
void A_04(void) { a <<= 4; a += 0x04; } void A_05(void) { a <<= 4; a += 0x05; }
void A_06(void) { a <<= 4; a += 0x06; } void A_07(void) { a <<= 4; a += 0x07; }
void A_08(void) { a <<= 4; a += 0x08; } void A_09(void) { a <<= 4; a += 0x09; }
void A_0A(void) { a <<= 4; a += 0x0A; } void A_0B(void) { a <<= 4; a += 0x0B; }
void A_0C(void) { a <<= 4; a += 0x0C; } void A_0D(void) { a <<= 4; a += 0x0D; }
void A_0E(void) { a <<= 4; a += 0x0E; } void A_0F(void) { a <<= 4; a += 0x0F; }
void D_00(void) { d <<= 4; d += 0x00; } void D_01(void) { d <<= 4; d += 0x01; }
void D_02(void) { d <<= 4; d += 0x02; } void D_03(void) { d <<= 4; d += 0x03; }
void D_04(void) { d <<= 4; d += 0x04; } void D_05(void) { d <<= 4; d += 0x05; }
void D_06(void) { d <<= 4; d += 0x06; } void D_07(void) { d <<= 4; d += 0x07; }
void D_08(void) { d <<= 4; d += 0x08; } void D_09(void) { d <<= 4; d += 0x09; }
void D_0A(void) { d <<= 4; d += 0x0A; } void D_0B(void) { d <<= 4; d += 0x0B; }
void D_0C(void) { d <<= 4; d += 0x0C; } void D_0D(void) { d <<= 4; d += 0x0D; }
void D_0E(void) { d <<= 4; d += 0x0E; } void D_0F(void) { d <<= 4; d += 0x0F; }

// action
void(*Rx_Fun[])(void) = // matrix bus message character vector table
{
    Spare, Spare, Spare, Spare, Spare, Spare, Spare, Spare, // 0x00 - 0x07 nul, soh, stx, etx, eot, enq, ack, bel
    Spare, Spare, Eol,   Spare, Spare, Spare, Spare, Spare, // 0x08 - 0x0f  bs, tab,  lf,  vt,  ff,  cr,  so,  si
    Spare, Spare, Spare, Spare, Spare, Spare, Spare, Spare, // 0x10 - 0x17 dle, dc1, dc2, dc3, dc4, nak, syn, etb
    Spare, Spare, Spare, Spare, Spare, Spare, Spare, Spare, // 0x18 - 0x1f can,  em, sub, esc,  fs,  gs,  rs,  us
    Spare, Spare, Spare, Spare, Spare, Spare, Test,  Spare, // 0x20 - 0x27 ' ', '!', '"', '#', '$', '%', '&', '''
    Spare, Spare, Spare, Spare, Spare, Tick,  BlkOf, IgnOn, // 0x28 - 0x2f '(', ')', '*', '+', ',', '-', '.', '/'
    D_00,  D_01,  D_02,  D_03,  D_04,  D_05,  D_06,  D_07,  // 0x30 - 0x37 '0', '1', '2', '3', '4', '5', '6', '7'
    D_08,  D_09,  BlkOn, HlpOf, Spare, Spare, Spare, HlpOn, // 0x38 - 0x3f '8', '9', ':', ';', '<', '=', '>', '?'
    Spare, D_0A,  D_0B,  D_0C,  D_0D,  D_0E,  D_0F,  Spare, // 0x40 - 0x47 '@', 'A', 'B', 'C', 'D', 'E', 'F', 'G'
    Spare, Spare, Spare, Spare, Spare, Spare, Spare, Spare, // 0x48 - 0x4f 'H', 'I', 'J', 'K', 'L', 'M', 'N', 'O'
    Spare, Spare, Spare, Spare, Spare, Spare, Spare, Spare, // 0x50 - 0x57 'P', 'Q', 'R', 'S', 'T', 'U', 'V', 'W'
    Spare, Spare, Spare, Spare, Spare, Spare, Spare, Spare, // 0x58 - 0x5f 'X', 'Y', 'Z', '[', '\', ']', '^', '_'
    Spare, D_0A,  D_0B,  D_0C,  D_0D,  D_0E,  D_0F,  Spare, // 0x60 - 0x67 ''', 'a', 'b', 'c', 'd', 'e', 'f', 'g'
    A_00,  A_01,  A_02,  A_03,  A_04,  A_05,  A_06,  A_07,  // 0x68 - 0x6f 'h', 'i', 'j', 'k', 'l', 'm', 'n', 'o'
    A_08,  A_09,  A_0A,  A_0B,  A_0C,  A_0D,  A_0E,  A_0F,  // 0x70 - 0x77 'p', 'q', 'r', 's', 't', 'u', 'v', 'w'
    Spare, Spare, Spare, Spare, MfOf,  Spare, MfOn,  Spare, // 0x78 - 0x7f 'x', 'y', 'z', '{', '|', '}', '~', del
}
;

// interrupt
// 2026-08-19 rev C bring-up fix (same bug as MH1 USART2 ISR): the original
// blocking UART1_Read() wedges permanently when this IRQ fires on an error
// flag (ORE from host-traffic bursts) with no RXNE pending — HAL_UART_Receive
// spins on HAL_GetTick, and SysTick (lowest priority) cannot advance inside
// this handler, so the 100ms timeout never expires and the MCU goes deaf.
// Non-blocking register read instead; error flags cleared explicitly.
// Original (rev A behaviour, kept for reference):
//	Rx_Fun[UART1_Read() & 0x7f](); // accept only ascii characters (0-128), store or execute bus message, byte-by-byte
void Uart1_Int()
{
    while (USART1->ISR & USART_ISR_RXNE)
    {
        Rx_Fun[USART1->RDR & 0x7f](); // accept only ascii characters (0-128), store or execute bus message, byte-by-byte
    }
    USART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NCF | USART_ICR_PECF;
}
