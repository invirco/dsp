// matrix.cs include in H1S1 DSP -- rev D card (U7 = STM32G0B1RET6), S174
//
// The panel-bus side of the rev C H1S1 (MW/D24/FW/H1S1/Core/Inc/matrix.cs),
// unchanged in protocol: the same per-character vector table, the same
// S2/S3/BUSY handshake, the same address/data nibble coding and the same
// test message. What rev D drops (S173 rulings Q5, and the card itself):
//   - the AK4619 path (StartAK4619, CodecPoll, the Sys001Test001/002 codec
//     cells): !CS_C is driven by the CM4's CS6 on rev D, U7 is off the net,
//     and the app owns the codec there;
//   - TestMicPres: !CS_M is the CM4's CS5 and U7 only sees it as an input;
//   - SPI1 altogether, so nothing here can ever put traffic on the wire the
//     CM4 boots the DSPs over;
//   - the PSU monitor (never read on rev C either; removed from the card).
// What rev D adds: the board-revision cell (dsp_card_rev.h) and RST_O.

// include
#include <string.h>
#include "matrix.h"          // the generated cell table, shared with rev C
#include "dsp_card_rev.h"

// THE REVISION CELL IS NOT IN DEFS YET. Sys001DspCardRev001 is the S173
// proposal (proposals/CONTRACT-PROPOSAL-S173.md, ruled Q1 (a) 2026-10-25);
// the hub lands it in defs and the app's pack tool regenerates matrix.h.
// Until then there is no address to put on the bus, so the cell is built
// only when matrix.h defines it: the image built today reports nothing, as
// rev C does, and still reads the straps (dspCardRev, for SWD). The build
// with the cell is compile-checked with a placeholder address (README).
#ifdef Sys001DspCardRev001
#define H1S1_REV_CELL 1
#else
#define H1S1_REV_CELL 0
#endif
#define DSP_CARD_REV_REQUEST 0xFF   // write 0xFF = "send it again"

// matrix start
const unsigned int MATRIX[] = // local matrix cells
{
   0x0, // reserved and unused
   Sys001Enc001,
   Sys001Skin001,
#if H1S1_REV_CELL
   Sys001DspCardRev001,
#endif
};
enum // MATRIX cell pointers
{
   p0, // reserved and unused
   pSys001Enc001,
   pSys001Skin001,
#if H1S1_REV_CELL
   pSys001DspCardRev001,
#endif
   MATRIX_X,
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
/* THE ANNOUNCEMENT NAMES THE SILICON AND THE STRAPS (S174). Rev C sends
 * "// H1S1 DSP"; this image sends "// H1S1 DSP G0B1 rev <code>", the code
 * patched in at MainInit. Each image runs only on its own part, so the line
 * is a positive card identification today, before the revision cell is in
 * defs -- tools/pi/dspcard_id.py reads it for the flash guard. The app
 * matches announcements with Contains("H1S1") (mx26 Boot.Protocol.cs), so
 * the longer line still verifies the MCU. */
char testMessage[100] = "// H1S1 DSP G0B1 rev ?\n";  // test message
#define TEST_MESSAGE_REV_AT 21                       // index of the '?'
unsigned int a = 0;							        // matrix address
unsigned char d = 0;						        // matrix data
unsigned int TXptr = 1;
volatile unsigned char dspCardRev = 0;              // REV_ID2..0 as read at boot

// typedef
GPIO_InitTypeDef GPIO_InitStruct = { 0 };           // hal gpio
GPIO_InitTypeDef GPIO_BusyStruct = { 0 };           // hal gpio

// extern
extern UART_HandleTypeDef huart1;

void TestMessage(void);
void RevCellPoll(void);

// function
void Poll(void) // TX, check if any cell data, or test message is flagged to send
{
    if (test) { HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_RESET); } // if test message is ready, set data ready flag to H mcu
    if (matrix[TXptr][TXF]) { HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_RESET); } // set ready flag
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
        while (HAL_GPIO_ReadPin(S3_GPIO_Port, S3_Pin)) { } // wait for MH MCU data request reset to avoid bus contention
    }
}

/* THE REVISION CELL (S173 proposal, ruled Q1 (a)): value = the strap code
 * (rev D = 1), read-only, reported once at boot; a write of 0xFF asks for
 * it again. The reply (0..7) can never equal the request, so H1S1 hearing
 * its own reply on the multi-drop bus cannot re-trigger it -- the S81
 * free-run (rev C matrix.cs, CodecPoll) cannot happen on this cell. Any
 * other value written is dropped: the cell is the card's, not the host's.
 * Poll() sends a TXD of 0 as the address alone; code 0 is never rev D. */
void RevCellPoll(void)
{
#if H1S1_REV_CELL
    if (matrix[pSys001DspCardRev001][RXF])
    {
        if (matrix[pSys001DspCardRev001][RXD] == DSP_CARD_REV_REQUEST)
        {
            matrix[pSys001DspCardRev001][TXD] = dspCardRev;
            matrix[pSys001DspCardRev001][TXF] = 1;
        }
        matrix[pSys001DspCardRev001][RXF] = 0;
    }
#endif
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
    // card revision straps: once, pulls off (DSPC-L11 Q3)
    dspCardRev = dsp_card_rev_read();
    testMessage[TEST_MESSAGE_REV_AT] = (char)('0' + dspCardRev);
#if H1S1_REV_CELL
    matrix[pSys001DspCardRev001][TXD] = dspCardRev;
    matrix[pSys001DspCardRev001][TXF] = 1;      // report once
#endif
    // main init
    // reset converters and mic pre shift registers (RST_C), and the option
    // cards (RST_O): U7 is the only RST_C driver on rev D (S173-3)
    HAL_GPIO_WritePin(RST_C_GPIO_Port, RST_C_Pin | RST_O_Pin, GPIO_PIN_RESET);
    HAL_Delay(100);
    HAL_GPIO_WritePin(RST_C_GPIO_Port, RST_C_Pin | RST_O_Pin, GPIO_PIN_SET);
    HAL_Delay(100);
}

void MainLoop()
{
    if (s_blink != s_blink1)
    {
        if (s_blink) { HAL_GPIO_WritePin(BLINK_GPIO_Port, BLINK_Pin, GPIO_PIN_SET); }      // blink on
        else { HAL_GPIO_WritePin(BLINK_GPIO_Port, BLINK_Pin, GPIO_PIN_RESET); }            // blink off
        s_blink1 = s_blink;
    }
    Poll();
    RevCellPoll();
}

// matrix functions
void Spare(void) { }
void Meter(void) { }                        // legacy allocation to control meter ballistics, instead of dsp control
void MfOn(void) { matrixFill = 1; }         // start matrix fill mode
void MfOf(void) { }                         // stop matrix fill mode
void BlkOn(void) { s_blink = 1; Meter(); }  // blink on
void BlkOf(void) { s_blink = 0; Meter(); }  // blink off
void Tick(void) { Meter(); }                // unused legacy tick counter
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
void Uart1_Rx(char c)
{
    Rx_Fun[c & 0x7f](); // accept only ascii characters (0-128), store or execute bus message, byte-by-byte
}
