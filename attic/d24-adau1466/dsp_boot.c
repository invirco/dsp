// C code to boot SigmaDSPs using code generated from SigmaStudio
// note: requires SPI enabled 

// install bcm2835 lib
// more info at: http://www.airspayce.com/mikem/bcm2835/index.html
// cd ~
// wget http://www.airspayce.com/mikem/bcm2835/bcm2835-1.75.tar.gz // was 1.69
// tar zxvf bcm2835-1.75.tar.gz
// cd bcm2835-1.75
// ./configure
// make
// sudo make check
// sudo make install
// build this c file using: gcc /home/app/dsp_boot.c -o /home/app/dsp_boot -l bcm2835
// raspi-gpio get to check all pin status
// run code: sudo /home/app/dsp_boot

#include <time.h>
#include <stdint.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/ioctl.h>
#include <sys/stat.h>
#include <linux/types.h>
#include <bcm2835.h>

// DSP addresses
#define DEVICE_ADDR_IC_1 0
#define DEVICE_ADDR_IC_2 1
#define DEVICE_ADDR_IC_3 2
#define DEVICE_ADDR_IC_4 3
#define DEVICE_ADDR_IC_5 4
#define DEVICE_ADDR_IC_6 5
#define DEVICE_ADDR_IC_7 6
#define DEVICE_ADDR_IC_8 7

//#include "SigmaStudioFW.h"
#include "DSP_IC_1.h"
#include "DSP_IC_1_PARAM.h"
//#include "DSP_IC_1_REG.h"
#include "DSP_IC_2.h"
#include "DSP_IC_2_PARAM.h"
//#include "DSP_IC_2_REG.h"
#include "DSP_IC_3.h"
#include "DSP_IC_3_PARAM.h"
//#include "DSP_IC_3_REG.h"
#include "DSP_IC_4.h"
#include "DSP_IC_4_PARAM.h"
//#include "DSP_IC_4_REG.h"
#include "DSP_IC_5.h"
#include "DSP_IC_5_PARAM.h"
//#include "DSP_IC_5_REG.h"
#include "DSP_IC_6.h"
#include "DSP_IC_6_PARAM.h"
//#include "DSP_IC_6_REG.h"
#include "DSP_IC_7.h"
#include "DSP_IC_7_PARAM.h"
//#include "DSP_IC_7_REG.h"
#include "DSP_IC_8.h"
#include "DSP_IC_8_PARAM.h"
//#include "DSP_IC_8_REG.h"

// DSP SPI chip selects
#define DSP1_CS 6
#define DSP2_CS 24
#define DSP3_CS 8
#define DSP4_CS 12
#define DSP5_CS 27
#define DSP6_CS 17
#define DSP7_CS 5
#define DSP8_CS 13
#define RST_D 16

// LED test
char dspLedOff[2] = {0x0, 0x0};
char dspLedOn[2] = {0x0, 0x1};
char dspCs;

void SIGMA_WRITE_REGISTER_BLOCK( char slaveAddress, int dspAddressInt, int numBytes, unsigned char bytePtr[] )
{
	delay(1);
	bcm2835_gpio_write(dspCs, LOW);
	delay(1);
	int i = 0;
	char buffer[numBytes + 3];
	buffer[0] = 0; 
	buffer[1] = dspAddressInt >>8; buffer[2] = dspAddressInt & 0xff;
	printf("\n%04X:", dspAddressInt);
	for (i = 0; i < numBytes; i++) 
	{ 
		buffer[i + 3] = bytePtr[i]; 
		printf(" %02X", bytePtr[i]);
	}
	bcm2835_spi_writenb(buffer, numBytes + 3); // was sizeof(buffer)
	delay(1);	
	bcm2835_gpio_write(dspCs, HIGH);
	delay(1);
}

void SIGMA_WRITE_DELAY( char slaveAddress, int delayAdd, int numBytes, unsigned char delayTable[] )
{
	/*
	// delayAdd is dummy byte? added in SigmaStudio+?
	int i = 0; int ms = 0;
	for (i = 0; i < numBytes; i++)
	{
		ms <<= 8; ms += delayTable[i];
	}
	*/
	//delay(110000);
	delay(11); // max delay
	printf("\nwrite delay...\n");
}

int main(int argc, char *argv[])
{
	int ret = 0; 

	boot_dsps();
	
	return ret;

	while(1)
	{

	}

	//return ret;
}

void boot_dsps()
{
	// init bcm2835 library
	bcm2835_init();
	// init spi
	bcm2835_spi_begin(); // start spi operation
	bcm2835_spi_chipSelect(BCM2835_SPI_CS_NONE); // disable default spi chip selects, use gpio
	bcm2835_spi_set_speed_hz(100000); // bit rate in Hz
	bcm2835_spi_setDataMode(BCM2835_SPI_MODE3);
	// configure gpio chip selects after spi init
	bcm2835_gpio_fsel(RST_D, BCM2835_GPIO_FSEL_OUTP); bcm2835_gpio_write(RST_D, LOW);
	bcm2835_gpio_fsel(DSP1_CS, BCM2835_GPIO_FSEL_OUTP); bcm2835_gpio_write(DSP1_CS, HIGH);
	bcm2835_gpio_fsel(DSP2_CS, BCM2835_GPIO_FSEL_OUTP); bcm2835_gpio_write(DSP2_CS, HIGH);
	bcm2835_gpio_fsel(DSP3_CS, BCM2835_GPIO_FSEL_OUTP); bcm2835_gpio_write(DSP3_CS, HIGH);
	bcm2835_gpio_fsel(DSP4_CS, BCM2835_GPIO_FSEL_OUTP); bcm2835_gpio_write(DSP4_CS, HIGH);
	bcm2835_gpio_fsel(DSP5_CS, BCM2835_GPIO_FSEL_OUTP); bcm2835_gpio_write(DSP5_CS, HIGH);
	bcm2835_gpio_fsel(DSP6_CS, BCM2835_GPIO_FSEL_OUTP); bcm2835_gpio_write(DSP6_CS, HIGH);
	bcm2835_gpio_fsel(DSP7_CS, BCM2835_GPIO_FSEL_OUTP); bcm2835_gpio_write(DSP7_CS, HIGH);
	bcm2835_gpio_fsel(DSP8_CS, BCM2835_GPIO_FSEL_OUTP); bcm2835_gpio_write(DSP8_CS, HIGH);
	// toggle reset
	delay(100); bcm2835_gpio_write(RST_D, HIGH);
	// boot dsp 1
	printf("\n\n// download DSP1 *********************************\n");
	bcm2835_gpio_write(DSP1_CS, LOW); delay(1); bcm2835_gpio_write(DSP1_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP1_CS, LOW); delay(1); bcm2835_gpio_write(DSP1_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP1_CS, LOW); delay(1); bcm2835_gpio_write(DSP1_CS, HIGH); delay(1);
	dspCs = DSP1_CS; 
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOn);
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOff);
	default_download_IC_1();
	delay(1); SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF520, 2, dspLedOn); delay(1);
	// boot dsp 2
	printf("\n\n// download DSP2 *********************************\n");
	bcm2835_gpio_write(DSP2_CS, LOW); delay(1); bcm2835_gpio_write(DSP2_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP2_CS, LOW); delay(1); bcm2835_gpio_write(DSP2_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP2_CS, LOW); delay(1); bcm2835_gpio_write(DSP2_CS, HIGH); delay(1);
	dspCs = DSP2_CS; 
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOn);
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOff);
	default_download_IC_2();	
	delay(1); SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF520, 2, dspLedOn); delay(1);
	// boot dsp 3
	printf("\n\n// download DSP3 *********************************\n");
	bcm2835_gpio_write(DSP3_CS, LOW); delay(1); bcm2835_gpio_write(DSP3_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP3_CS, LOW); delay(1); bcm2835_gpio_write(DSP3_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP3_CS, LOW); delay(1); bcm2835_gpio_write(DSP3_CS, HIGH); delay(1);
	dspCs = DSP3_CS; 
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOn);
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOff);
	default_download_IC_3();	
	delay(1); SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF520, 2, dspLedOn); delay(1);
	// boot dsp 4
	printf("\n\n// download DSP4 *********************************\n");
	bcm2835_gpio_write(DSP4_CS, LOW); delay(1); bcm2835_gpio_write(DSP4_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP4_CS, LOW); delay(1); bcm2835_gpio_write(DSP4_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP4_CS, LOW); delay(1); bcm2835_gpio_write(DSP4_CS, HIGH); delay(1);
	dspCs = DSP4_CS; 
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOn);
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOff);
	default_download_IC_4();	
	delay(1); SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF520, 2, dspLedOn); delay(1);
	// boot dsp 5
	printf("\n\n// download DSP5 *********************************\n");
	bcm2835_gpio_write(DSP5_CS, LOW); delay(1); bcm2835_gpio_write(DSP5_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP5_CS, LOW); delay(1); bcm2835_gpio_write(DSP5_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP5_CS, LOW); delay(1); bcm2835_gpio_write(DSP5_CS, HIGH); delay(1);
	dspCs = DSP5_CS; 
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOn);
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOff);
	default_download_IC_5();	
	delay(1); SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF520, 2, dspLedOn); delay(1);
	// boot dsp 6
	printf("\n\n// download DSP6 *********************************\n");
	bcm2835_gpio_write(DSP6_CS, LOW); delay(1); bcm2835_gpio_write(DSP6_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP6_CS, LOW); delay(1); bcm2835_gpio_write(DSP6_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP6_CS, LOW); delay(1); bcm2835_gpio_write(DSP6_CS, HIGH); delay(1);
	dspCs = DSP6_CS; 
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOn);
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOff);
	default_download_IC_6();	
	delay(1); SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF520, 2, dspLedOn); delay(1);
	// boot dsp 7
	printf("\n\n// download DSP7 *********************************\n");
	bcm2835_gpio_write(DSP7_CS, LOW); delay(1); bcm2835_gpio_write(DSP7_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP7_CS, LOW); delay(1); bcm2835_gpio_write(DSP7_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP7_CS, LOW); delay(1); bcm2835_gpio_write(DSP7_CS, HIGH); delay(1);
	dspCs = DSP7_CS; 
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOn);
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOff);
	default_download_IC_7();	
	delay(1); SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF520, 2, dspLedOn); delay(1);
	// boot dsp 8
	printf("\n\n// download DSP8 *********************************\n");
	bcm2835_gpio_write(DSP8_CS, LOW); delay(1); bcm2835_gpio_write(DSP8_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP8_CS, LOW); delay(1); bcm2835_gpio_write(DSP8_CS, HIGH); delay(1);
	bcm2835_gpio_write(DSP8_CS, LOW); delay(1); bcm2835_gpio_write(DSP8_CS, HIGH); delay(1);
	dspCs = DSP8_CS; 
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOn);
	SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF899, 2, dspLedOff);
	default_download_IC_8();	
	delay(1); SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF520, 2, dspLedOn);delay(1);
	// release gpio chip selects for MCU use
	bcm2835_gpio_set_pud(DSP1_CS, BCM2835_GPIO_PUD_UP); bcm2835_gpio_fsel(DSP1_CS, BCM2835_GPIO_FSEL_INPT);
	bcm2835_gpio_set_pud(DSP2_CS, BCM2835_GPIO_PUD_UP);	bcm2835_gpio_fsel(DSP2_CS, BCM2835_GPIO_FSEL_INPT);
	bcm2835_gpio_set_pud(DSP3_CS, BCM2835_GPIO_PUD_UP); bcm2835_gpio_fsel(DSP3_CS, BCM2835_GPIO_FSEL_INPT);
	bcm2835_gpio_set_pud(DSP4_CS, BCM2835_GPIO_PUD_UP);	bcm2835_gpio_fsel(DSP4_CS, BCM2835_GPIO_FSEL_INPT);
	bcm2835_gpio_set_pud(DSP5_CS, BCM2835_GPIO_PUD_UP); bcm2835_gpio_fsel(DSP5_CS, BCM2835_GPIO_FSEL_INPT);
	bcm2835_gpio_set_pud(DSP6_CS, BCM2835_GPIO_PUD_UP);	bcm2835_gpio_fsel(DSP6_CS, BCM2835_GPIO_FSEL_INPT);
	bcm2835_gpio_set_pud(DSP7_CS, BCM2835_GPIO_PUD_UP); bcm2835_gpio_fsel(DSP7_CS, BCM2835_GPIO_FSEL_INPT);
	bcm2835_gpio_set_pud(DSP8_CS, BCM2835_GPIO_PUD_UP);	bcm2835_gpio_fsel(DSP8_CS, BCM2835_GPIO_FSEL_INPT);
	// release spi pins for MCU use
	bcm2835_spi_end(); // end spi operation
	printf("\n\n// finished *********************************\n\n");
}