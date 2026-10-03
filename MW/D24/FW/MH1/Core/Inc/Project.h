#ifndef PROJECT_H
#define PROJECT_H

/* HEADER:

   Filename:      project.h
   Description:   project header and definition file
   Author:        Peter Watts
   Revision:      Stonepower_DSP3-20210910202640
*/

#define PROJECT_NAME "MW D24"
#define FW_REV "Stonepower_DSP3-20210910202640"
#define HOST_BAUD 115200 // system UART baud rates max 115200, 230400, 460800, 921600
#define SYSTEM_BAUD 115200 // system UART baud rates

/* INITIALIZATION: used after system power-up.

   Master MCU and Host are connected by full duplex serial port.
   After MCU network is self-configured, Master MCU will send power up message to Host, example as follows:
   
   // Product Name   : Mickle_M3218
   // MCU M FW rev   : 1.000
   // Valid Serial   : 2d805f616f82f1e177479607

   After Host has received power up message, it can send a S_SCAN message to Master MCU.
   If Master MCU receives S_SCAN message it will return a list of all MCUs in the system, example as follows:
   
   // scanning hardware
   // Product Name   : Mickle_M3218
   // MCU M FW rev   : 1.000
   // Valid Serial   : 2d805f616f82f1e177479607
   // found      PCB1: M3218 DSP                MCU H1
   //            Ser : 50ff6e067875504940281367 Rev : 1.000
   // found      PCB1: M3218 DSP                MCU H1S1
   // found      PCB2: M3218 Fader Left         MCU H2
   //            Ser : 50ff6e067875504943381367 Rev : 1.000
   // found      PCB2: M3218 Fader Left         MCU H2S1
   // found      PCB2: M3218 Fader Left         MCU H2S2
   // found      PCB2: M3218 Fader Left         MCU H2S3 
   etc...
   // found      PCB5: M3218 Fat Channel Right  MCU H7
   //            Ser : 50ff6c067875504942361367 Rev : 1.000
   // found      PCB5: M3218 Fat Channel Right  MCU H7S1
   // found      PCB5: M3218 Fat Channel Right  MCU H7S2
   // found      PCB5: M3218 Fat Channel Right  MCU H7S3
   // hardware scan complete
   
   This hardware scan response includes key information such as product name, system valid serial number, 
   hard-coded firmware revisions, PCB reference numbers, MCU IDs, and if each MCU is found or missing.
   
   After receiving this information the Host can determine if the Vaid Serial is authourised and if OK 
   start normal system operation by sending S_RUN message.
   When Master MCU receives the S_RUN message, it will return a list of all MCUs with ID and 
   firmware revisions, example as follows:
   
   // resuming normal operation
+
   // H2S1 Mickle_M3218-20190605064533
   // H2S2 Mickle_M3218-20190605064533
   // H4S1 Mickle_M3218-20190605064533
   etc...
   // H5S3 Mickle_M3218-20190605064533
   // H5S4 Mickle_M3218-20190605064533
   // H5S5 Mickle_M3218-20190605064533

   If a later firmware revision is available, Host has option to update all MCU firmware.
   Updating firmware starts by rebooting the system with S_RESET message.
   After system has rebooted, Host can enter update mode by sending S_FLASH message to Master MCU.
   Master MCU will then return S_FLASH message to Host to begin firmware update.
   Host sends MCU firmware file one line at a time and waits for Master MCU to respond with 
   S_FLASH message before sending the next data record.
   This process is repeated until Host reaches the end of the firmware update file.
   Firmware update operation is complete when Host receives "// flash end of firmware record".

*/

// SYSTEM MESSAGE CHARACTERS note: all system message characters followed by '\n'

#define S_BLINK_ON        			':' // Blink LEDs on in sync, from hardware to Host.
#define S_BLINK_OFF					'.' // Blink LEDs off in sync, from hardware to Host.
#define S_COMMENT						'/' // Non-executable system message from hardware to Host.
#define S_CXD							',' // Channel Extended Data flag, part of CFID message string, loads appended data bytes into consecutive channels
#define S_DATA							'=' // CFI Data value request to Host from connected devices. 
#define S_DIMI							'>' // Increase LED brightness, from Host to Hardware.
#define S_DIMD							'<' // Decrease LED brightness, From Host to Hardware.
#define S_ERROR						'!' // Reserved for system error messages from hardware to Host.
#define S_FLASH						'#' // Flash update request from Host, then record requests from hardware.
#define S_HELP_ON						'?' // System help mode on, entered by hardware or Host.
#define S_HELP_OFF					';' // System help mode off, ended by hardware or Host. 
#define S_RESET						'*' // Hardware reset.
#define S_RUN							'+' // Normal operation mode (from Host), and request for new CFI data (from hardware).
#define S_SCAN							'$' // Hardware status scan, request from Host.
#define S_TICK							'-' // System Tick = 100mS time tick for synchronizing meters etc.
#define S_TEST							'&' // Reserved for system test messages.
#define S_ECHO							'@' // Echo MH1 messages to H1S1, bi-directional.

// additional tokens to reduce complete matrix data load time
#define S_FILL_START				'~' // Start Matrix complete data fill
#define S_FILL_STOP					'|' // Stop Matrix complete data fill

/* NORMAL OPERATION:
   Host waits for S_RUN token from Master MCU before sending new data message.
   
   Master MCU will poll all MCUs in network, and broadcast data messages before requesting new data from Host.
   All MAIN PROTOCOL messages are echoed to Wifi network devices by Host.
   '\n'         Single EOL/Newline char '\n' or byte 0x0A.
*/

// defines from def.numbers/other/defines
#define DSP_3  //DSP_3 conditions and modifications


// matrix data definitions
// d_Debug notes: bit definitions for Sys01_Debug01
#define d_Debug01_Bus 1
#define d_Debug01_DspRd 2
#define d_Debug01_DspWr 4
#define d_Debug01_DspData 8
#define d_Debug01_Fx 16
// Sys01_Debug02 = DSP ID e.q. 0x70, 0x72, 0x74, 0x76
// Sys01_Debug03 = DSP memory address MSB
// Sys01_Debug04 = DSP memory address LSB
// Sys01_Debug05 = number of bytes to read
// Sys01_Debug06 = number of read cycles at 100mS intervals
// d_ChSel
#define d_ChSel_Sys01 1
// d_BusBnk
#define d_BusBnk_01_08 1
#define d_BusBnk_09_16 2
#define d_BusBnk_Vca 3
// d_DsplyBnk
#define d_DsplyBnk_Aux01 1
#define d_DsplyBnk_Aux02 2
#define d_DsplyBnk_Dsp01 3
#define d_DsplyBnk_Dsp02 4
#define d_DsplyBnk_Mic01 5
#define d_DsplyBnk_Mic02 6
#define d_DsplyBnk_Phns01 7
#define d_DsplyBnk_Phns02 8
#define d_DsplyBnk_Spkr01 9
#define d_DsplyBnk_SPkr02 10
#define d_DsplyBnk_Talk 11
// d_EncBnk
#define d_EncBnk_Gain 1
#define d_EncBnk_Pan 2
// d_FdrBnk
#define d_FdrBnk_Ch01_16 0
#define d_FdrBnk_Ch17_32 1
#define d_FdrBnk_FxRet 2
#define d_FdrBnk_Bus 3
#define d_FdrBnk_Vca 4
// d_InBnk
#define d_InBnk_01 1
#define d_InBnk_02 2
// d_OutBnk
#define d_OutBnk_01 1
#define d_OutBnk_02 2
// d_PrstBnk
#define d_PrstBnk_01 1
#define d_PrstBnk_02 2
#define d_PrstBnk_03 3
#define d_PrstBnk_04 4
#define d_PrstBnk_05 5
#define d_PrstBnk_06 6
#define d_PrstBnk_07 7
#define d_PrstBnk_08 8
// d_SndBnk
#define d_SndBnk_01_04 1
#define d_SndBnk_05_08 2
#define d_SndBnk_09_12 3
#define d_SndBnk_13_16 4
#define d_SndBnk_Fx01_04 5
// d_SndMuteMode
#define d_SndMuteMode_PreFdr 1
#define d_SndMuteMode_PstFdr 2
// d_SndPrePstMode
#define d_SndPrePstMode_Pre 1
#define d_SndPrePstMode_Post 2
// d_SpkrBnk
#define d_SpkrBnk_01 1
#define d_SpkrBnk_02 2
// d_SwBnk
#define d_SwBnk_Eq 1
#define d_SwBnk_Dyn 2
#define d_SwBnk_Outs 3
#define d_SwBnk_Fx 4
#define d_SwBnk_Meter 5
#define d_SwBnk_Mutes 6
#define d_SwBnk_RecPlay 7
#define d_SwBnk_Talk 8
#define d_SwBnk_Setup 9
#define d_SwBnk_User 10
#define d_SwBnk_Files 11
#define d_SwBnk_Help 12
// d_VcaAss
#define d_VcaAss_00 0
#define d_VcaAss_01 1
#define d_VcaAss_02 2
#define d_VcaAss_03 3
#define d_VcaAss_04 4
#define d_VcaAss_05 5
#define d_VcaAss_06 6
#define d_VcaAss_07 7
#define d_VcaAss_08 8
// d24
#define d24_Enc_L 0
#define d24_Enc_C 64
#define d24_Enc_R 128
#define d24_SwBnk_EQ 1
#define d24_SwBnk_MonoAux 2
#define d24_SwBnk_StereoAux 3
#define d24_SwBnk_FX 4
#define d24_SwBnk_Jake1 5
#define d24_SwBnk_Jake2 6
#define d24_SwBnk_Overview 7
#define d24_SwBnk_Home 8
#define d24_SwBnk_Menu 9
#define d24_SwBnk_48V 10
#define d24_SwBnk_Feedback 11
#define d24_SwBnk_ChAssign 12
#define d24_SwBnk_FxMute 13
#define d24_SwBnk_Mutes 14
#define d24_SwBnk_Scenes 15
#define d24_SwBnk_Phones 16
#define d24_SwBnk_RecPlay 17
#define d24_SwBnk_Monitor 18
#define d24_SwBnk_Greetings 19
// m3218 DSP bus assignments
#define m3218_Bus_MainL 0x14 // was I_BUS_Lc
#define m3218_Bus_MainR 0x13 // was I_BUS_Rc
#define m3218_Bus_MonL 0x16 // was I_BUS_MON_Lc
#define m3218_Bus_MonR 0x15 // was I_BUS_MON_Rc
#define m3218_Bus_Fx1 0x19 // was I_SEND_FX_1c
#define m3218_Bus_1 0x01 // was I_SEND_1c

// matrix address definitions
#define Address_0 0 // reserved
#define Sys01_BusBnk01 1 // 0x1, i
#define Sys01_ChSel01 2 // 0x2, j
#define Sys01_Debug01 3 // 0x3, k
#define Sys01_Debug02 4 // 0x4, l
#define Sys01_Debug03 5 // 0x5, m
#define Sys01_Debug04 6 // 0x6, n
#define Sys01_Debug05 7 // 0x7, o
#define Sys01_Debug06 8 // 0x8, p
#define Sys01_Debug07 9 // 0x9, q
#define Sys01_Debug08 10 // 0xA, r
#define Sys01_DsplyBnk01 11 // 0xB, s
#define Sys01_Enc01 12 // 0xC, t
#define Sys01_Enc02 13 // 0xD, u
#define Sys01_Enc03 14 // 0xE, v
#define Sys01_Enc04 15 // 0xF, w
#define Sys01_EncBnk01 16 // 0x10, ih
#define Sys01_EncSw01 17 // 0x11, ii
#define Sys01_EncSw02 18 // 0x12, ij
#define Sys01_EncSw03 19 // 0x13, ik
#define Sys01_EncSw04 20 // 0x14, il
#define Sys01_FdrBnk01 21 // 0x15, im
#define Sys01_FxBnk01 22 // 0x16, in
#define Sys01_MuteGrpOn01 23 // 0x17, io
#define Sys01_MuteGrpOn02 24 // 0x18, ip
#define Sys01_MuteGrpOn03 25 // 0x19, iq
#define Sys01_MuteGrpOn04 26 // 0x1A, ir
#define Sys01_SndBnk01 27 // 0x1B, is
#define Sys01_SndMuteMode01 28 // 0x1C, it
#define Sys01_SndPrePstMode01 29 // 0x1D, iu
#define Sys01_SndPrePstMode02 30 // 0x1E, iv
#define Sys01_SndPrePstMode03 31 // 0x1F, iw
#define Sys01_SndPrePstMode04 32 // 0x20, jh
#define Sys01_SndPrePstMode05 33 // 0x21, ji
#define Sys01_SndPrePstMode06 34 // 0x22, jj
#define Sys01_SndPrePstMode07 35 // 0x23, jk
#define Sys01_SndPrePstMode08 36 // 0x24, jl
#define Sys01_SndPrePstMode09 37 // 0x25, jm
#define Sys01_SndPrePstMode10 38 // 0x26, jn
#define Sys01_SndPrePstMode11 39 // 0x27, jo
#define Sys01_SndPrePstMode12 40 // 0x28, jp
#define Sys01_SndPrePstMode13 41 // 0x29, jq
#define Sys01_SndPrePstMode14 42 // 0x2A, jr
#define Sys01_SndPrePstMode15 43 // 0x2B, js
#define Sys01_SndPrePstMode16 44 // 0x2C, jt
#define Sys01_Sw01 45 // 0x2D, ju
#define Sys01_SwBnk01 46 // 0x2E, jv
#define MATRIX_SIZE 47

// matrix max definitions
#define Sys_BusBnk_Cmax 1
#define Sys_BusBnk_Fmax 1
#define Sys_ChSel_Cmax 1
#define Sys_ChSel_Fmax 1
#define Sys_Debug_Cmax 1
#define Sys_Debug_Fmax 8
#define Sys_DsplyBnk_Cmax 1
#define Sys_DsplyBnk_Fmax 1
#define Sys_Enc_Cmax 1
#define Sys_Enc_Fmax 4
#define Sys_EncBnk_Cmax 1
#define Sys_EncBnk_Fmax 1
#define Sys_EncSw_Cmax 1
#define Sys_EncSw_Fmax 4
#define Sys_FdrBnk_Cmax 1
#define Sys_FdrBnk_Fmax 1
#define Sys_FxBnk_Cmax 1
#define Sys_FxBnk_Fmax 1
#define Sys_MuteGrpOn_Cmax 1
#define Sys_MuteGrpOn_Fmax 4
#define Sys_SndBnk_Cmax 1
#define Sys_SndBnk_Fmax 1
#define Sys_SndMuteMode_Cmax 1
#define Sys_SndMuteMode_Fmax 1
#define Sys_SndPrePstMode_Cmax 1
#define Sys_SndPrePstMode_Fmax 16
#define Sys_Sw_Cmax 1
#define Sys_Sw_Fmax 1
#define Sys_SwBnk_Cmax 1
#define Sys_SwBnk_Fmax 1

#endif // PROJECT_H
