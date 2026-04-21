// C code to boot SigmaDSPs using code generated from SigmaStudio
// note: requires SPI enabled 

#include <time.h>
#include <stdint.h>
#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <getopt.h>
#include <fcntl.h>
#include <sys/ioctl.h>
#include <linux/ioctl.h>
#include <sys/stat.h>
#include <linux/types.h>
#include <linux/spi/spidev.h>

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
//#define PI_MCU_SPI 12

// Pin modes:
#define INPUT (0)
#define OUTPUT (1)
#define LOW (0)
#define HIGH (1)

#define ARRAY_SIZE(a) (sizeof(a) / sizeof((a)[0]))

typedef struct {
        int     pin;
        char*   fn;
} pin_t;

static pin_t pinopen(int pin, int mode);
static void pinclose(pin_t pin);
static void pinwrite(pin_t pin, int value);
static int pinread(pin_t pin);
static int boot(uint8_t *boot_file, int boot_file_size);
void Init_Cs();
int cs_pin, cs1_pin, cs2_pin, cs3_pin, cs4_pin, cs5_pin, cs6_pin, cs7_pin, cs8_pin;
int rst_pin;
//int pi_mcu_pin;

// LED test
char dspLedOn[2] = {0x0, 0x1};

static void pabort(const char *s)
{
	perror(s);
	abort();
}

static const char *device = "/dev/spidev0.0";
static uint32_t mode = 3 | SPI_NO_CS; // disable default chip select, provided by gpio control
static uint8_t bits = 8;
static char *input_file;
static char *output_file;
static uint32_t speed = 100000; // was 3000000
static uint16_t delay;
static int verbose = 1;

uint8_t old_file[] = {
	0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
	0x40, 0x00, 0x00, 0x00, 0x00, 0x95,
	0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
	0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
	0xFF, 0xFF, 0xFF, 0xFF, 0xFF, 0xFF,
	0xF0, 0x0D,
};

uint8_t default_tx[] = {
	 0,  1,   2,   3,   4,   5,   6,   7,   8,   9,   10,  11,  12,  13,  14,  15,
	16,  17,  18,  19,  20,  21,  22,  23,  24,  25,  26,  27,  28,  29,  30,  31,
	32,  33,  34,  35,  36,  37,  38,  39,  40,  41,  42,  43,  44,  45,  46,  47,
	48,  49,  50,  51,  52,  53,  54,  55,  56,  57,  58,  59,  60,  61,  62,  63,
	64,  65,  66,  67,  68,  69,  70,  71,  72,  73,  74,  75,  76,  77,  78,  79,
	80,  81,  82,  83,  84,  85,  86,  87,  88,  89,  90,  91,  92,  93,  94,  95,
	96,  97,  98,  99,  100, 101, 102, 103, 104, 105, 106, 107, 108, 109, 110, 111,
	112, 113, 114, 115, 116, 117, 118, 119, 120, 121, 122, 123, 124, 125, 126, 127,
	128, 129, 130, 131, 132, 133, 134, 135, 136, 137, 138, 139, 140, 141, 142, 143,
	144, 145, 146, 147, 148, 149, 150, 151, 152, 153, 154, 155, 156, 157, 158, 159,
	160, 161, 162, 163, 164, 165, 166, 167, 168, 169, 170, 171, 172, 173, 174, 175,
	176, 177, 178, 179, 180, 181, 182, 183, 184, 185, 186, 187, 188, 189, 190, 191,
	192, 193, 194, 195, 196, 197, 198, 199, 200, 201, 202, 203, 204, 205, 206, 207,
	208, 209, 210, 211, 212, 213, 214, 215, 216, 217, 218, 219, 220, 221, 222, 223,
	224, 225, 226, 227, 228, 229, 230, 231, 232, 233, 234, 235, 236, 237, 238, 239,
	240, 241, 242, 243, 244, 245, 246, 247, 248, 249, 250, 251, 252, 253, 254, 255,
};

uint8_t default_rx[120000] = {0, }; // set to max size of DSP memory
char *input_tx;

void SIGMA_WRITE_REGISTER_BLOCK( char slaveAddress, int dspAddressInt, int numBytes, unsigned char bytePtr[] )
{
	int i = 0;
	char buffer[numBytes + 3];
	buffer[0] = 0; buffer[1] = dspAddressInt >>8; buffer[2] = dspAddressInt & 0xff;
	for (i = 0; i < numBytes; i++) { buffer[i + 3] = bytePtr[i]; }
	boot(buffer, sizeof(buffer));
}

void SIGMA_WRITE_DELAY( char slaveAddress, int delayAdd, int numBytes, unsigned char delayTable[] )
{
	// delayAdd is dummy byte? added in SigmaStudio+?
	int i = 0; int ms = 0;
	for (i = 0; i < numBytes; i++)
	{
		ms <<= 8; ms += delayTable[i];
	}
	usleep(ms * 10);
}

void old_SIGMA_WRITE_DELAY( char slaveAddress, int numBytes, unsigned char delayTable[] )
{
	int i = 0; int ms = 0;
	for (i = 0; i < numBytes; i++)
	{
		ms <<= 8; ms += delayTable[i];
	}
	usleep(ms * 10);
}

static void hex_dump(const void *src, size_t length, size_t line_size,
		     char *prefix)
{
	int i = 0;
	const unsigned char *address = src;
	const unsigned char *line = address;
	unsigned char c;

	printf("%s | ", prefix);
	while (length-- > 0) {
		printf("%02X ", *address++);
		if (!(++i % line_size) || (length == 0 && i % line_size)) {
			if (length == 0) {
				while (i++ % line_size)
					printf("__ ");
			}
			printf(" | ");  /* right close */
			while (line < address) {
				c = *line++;
				printf("%c", (c < 33 || c == 255) ? 0x2E : c);
			}
			printf("\n");
			if (length > 0)
				printf("%s | ", prefix);
		}
	}
}

static int unescape(char *_dst, char *_src, size_t len)
{
	int ret = 0;
	int match;
	char *src = _src;
	char *dst = _dst;
	unsigned int ch;

	while (*src) {
		if (*src == '\\' && *(src+1) == 'x') {
			match = sscanf(src + 2, "%2x", &ch);
			if (!match)
				pabort("malformed input string");

			src += 4;
			*dst++ = (unsigned char)ch;
		} else {
			*dst++ = *src++;
		}
		ret++;
	}
	return ret;
}

static void transfer(int fd, uint8_t const *tx, uint8_t const *rx, size_t len)
{
	int ret;
	int out_fd;
	struct spi_ioc_transfer tr = {
		.tx_buf = (unsigned long)tx,
		.rx_buf = (unsigned long)rx,
		.len = len,
		.delay_usecs = delay,
		.speed_hz = speed,
		.bits_per_word = bits,
	};

	if (mode & SPI_TX_QUAD)
		tr.tx_nbits = 4;
	else if (mode & SPI_TX_DUAL)
		tr.tx_nbits = 2;
	if (mode & SPI_RX_QUAD)
		tr.rx_nbits = 4;
	else if (mode & SPI_RX_DUAL)
		tr.rx_nbits = 2;
	if (!(mode & SPI_LOOP)) {
		if (mode & (SPI_TX_QUAD | SPI_TX_DUAL))
			tr.rx_buf = 0;
		else if (mode & (SPI_RX_QUAD | SPI_RX_DUAL))
			tr.tx_buf = 0;
	}

	ret = ioctl(fd, SPI_IOC_MESSAGE(1), &tr);
	if (ret < 1)
		pabort("can't send spi message");

	if (verbose)
		hex_dump(tx, len, 32, "TX");

	if (output_file) {
		out_fd = open(output_file, O_WRONLY | O_CREAT | O_TRUNC, 0666);
		if (out_fd < 0)
			pabort("could not open output file");

		ret = write(out_fd, rx, len);
		if (ret != len)
			pabort("not all bytes written to output file");

		close(out_fd);
	}

	if (verbose || !output_file)
		hex_dump(rx, len, 32, "RX");
}

static void print_usage(const char *prog)
{
	printf("Usage: %s [-DsbdlHOLC3]\n", prog);
	puts("  -D --device   device to use (default /dev/spidev0.0)\n"
	     "  -s --speed    max speed (Hz)\n"
	     "  -d --delay    delay (usec)\n"
	     "  -b --bpw      bits per word\n"
	     "  -i --input    input data from a file (e.g. \"test.bin\")\n"
	     "  -o --output   output data to a file (e.g. \"results.bin\")\n"
	     "  -l --loop     loopback\n"
	     "  -H --cpha     clock phase\n"
	     "  -O --cpol     clock polarity\n"
	     "  -L --lsb      least significant bit first\n"
	     "  -C --cs-high  chip select active high\n"
	     "  -3 --3wire    SI/SO signals shared\n"
	     "  -v --verbose  Verbose (show tx buffer)\n"
	     "  -p            Send data (e.g. \"1234\\xde\\xad\")\n"
	     "  -N --no-cs    no chip select\n"
	     "  -R --ready    slave pulls low to pause\n"
	     "  -2 --dual     dual transfer\n"
	     "  -4 --quad     quad transfer\n");
	exit(1);
}

static void parse_opts(int argc, char *argv[])
{
	while (1) {
		static const struct option lopts[] = {
			{ "device",  1, 0, 'D' },
			{ "speed",   1, 0, 's' },
			{ "delay",   1, 0, 'd' },
			{ "bpw",     1, 0, 'b' },
			{ "cpol",    0, 0, 'O' },
			{ "input",   1, 0, 'i' },
			{ "output",  1, 0, 'o' },
			{ "loop",    0, 0, 'l' },
			{ "cpha",    0, 0, 'H' },
			{ "lsb",     0, 0, 'L' },
			{ "cs-high", 0, 0, 'C' },
			{ "3wire",   0, 0, '3' },
			{ "no-cs",   0, 0, 'N' },
			{ "ready",   0, 0, 'R' },
			{ "dual",    0, 0, '2' },
			{ "verbose", 0, 0, 'v' },
			{ "quad",    0, 0, '4' },
			{ NULL, 0, 0, 0 },
		};
		int c;

		c = getopt_long(argc, argv, "D:s:d:b:i:o:lHOLC3NR24p:v",
				lopts, NULL);

		if (c == -1)
			break;

		switch (c) {
		case 'D':
			device = optarg;
			break;
		case 's':
			speed = atoi(optarg);
			break;
		case 'd':
			delay = atoi(optarg);
			break;
		case 'b':
			bits = atoi(optarg);
			break;
		case 'i':
			input_file = optarg;
			break;
		case 'o':
			output_file = optarg;
			break;
		case 'l':
			mode |= SPI_LOOP;
			break;
		case 'H':
			mode |= SPI_CPHA;
			break;
		case 'O':
			mode |= SPI_CPOL;
			break;
		case 'L':
			mode |= SPI_LSB_FIRST;
			break;
		case 'C':
			mode |= SPI_CS_HIGH;
			break;
		case '3':
			mode |= SPI_3WIRE;
			break;
		case 'N':
			mode |= SPI_NO_CS;
			break;
		case 'v':
			verbose = 1;
			break;
		case 'R':
			mode |= SPI_READY;
			break;
		case 'p':
			input_tx = optarg;
			break;
		case '2':
			mode |= SPI_TX_DUAL;
			break;
		case '4':
			mode |= SPI_TX_QUAD;
			break;
		default:
			print_usage(argv[0]);
			break;
		}
	}
	if (mode & SPI_LOOP) {
		if (mode & SPI_TX_DUAL)
			mode |= SPI_RX_DUAL;
		if (mode & SPI_TX_QUAD)
			mode |= SPI_RX_QUAD;
	}
}

static void transfer_escaped_string(int fd, char *str)
{
	size_t size = strlen(str);
	uint8_t *tx;
	uint8_t *rx;

	tx = malloc(size);
	if (!tx)
		pabort("can't allocate tx buffer");

	rx = malloc(size);
	if (!rx)
		pabort("can't allocate rx buffer");

	size = unescape((char *)tx, str, size);
	transfer(fd, tx, rx, size);
	free(rx);
	free(tx);
}

static void transfer_file(int fd, char *filename)
{
	ssize_t bytes;
	struct stat sb;
	int tx_fd;
	uint8_t *tx;
	uint8_t *rx;

	if (stat(filename, &sb) == -1)
		pabort("can't stat input file");

	tx_fd = open(filename, O_RDONLY);
	if (tx_fd < 0)
		pabort("can't open input file");

	tx = malloc(sb.st_size);
	if (!tx)
		pabort("can't allocate tx buffer");

	rx = malloc(sb.st_size);
	if (!rx)
		pabort("can't allocate rx buffer");

	bytes = read(tx_fd, tx, sb.st_size);
	if (bytes != sb.st_size)
		pabort("failed to read input file");

	transfer(fd, tx, rx, sb.st_size);
	free(rx);
	free(tx);
	close(tx_fd);
}

int main(int argc, char *argv[])
{
	//pi_mcu_pin = PI_MCU_SPI; pin_t pi_mcu = pinopen(pi_mcu_pin, OUTPUT);
	//pinwrite(pi_mcu, LOW); // PI controls SPI CLK/MOSI/MISO

	cs3_pin = 8; pin_t dsp3_cs = pinopen(cs3_pin, OUTPUT); pinwrite(dsp3_cs, LOW); 

	// set all cs pins as high outputs
	//cs1_pin = DSP1_CS; pin_t dsp1_cs = pinopen(cs1_pin, OUTPUT); pinwrite(dsp1_cs, HIGH);
	//cs2_pin = DSP2_CS; pin_t dsp2_cs = pinopen(cs2_pin, OUTPUT); pinwrite(dsp2_cs, HIGH); 
	//cs3_pin = DSP3_CS; pin_t dsp3_cs = pinopen(cs3_pin, OUTPUT); pinwrite(dsp3_cs, LOW); 
	//cs4_pin = DSP4_CS; pin_t dsp4_cs = pinopen(cs4_pin, OUTPUT); pinwrite(dsp4_cs, HIGH); 
	//cs5_pin = DSP5_CS; pin_t dsp5_cs = pinopen(cs5_pin, OUTPUT); pinwrite(dsp5_cs, HIGH); 
	//cs6_pin = DSP6_CS; pin_t dsp6_cs = pinopen(cs6_pin, OUTPUT); pinwrite(dsp6_cs, HIGH); 
	//cs7_pin = DSP7_CS; pin_t dsp7_cs = pinopen(cs7_pin, OUTPUT); pinwrite(dsp7_cs, HIGH); 
	//cs8_pin = DSP8_CS; pin_t dsp8_cs = pinopen(cs8_pin, OUTPUT); pinwrite(dsp8_cs, HIGH); 

	return;

	// toggle reset
	rst_pin = RST_D; pin_t rst_d = pinopen(rst_pin, OUTPUT);
	pinwrite(rst_d, LOW); // reset DSPs
	sleep(0.1); 
	pinwrite(rst_d, HIGH); 

	int ret = 0; 
	printf("\n// download DSP1 *********************************\n\n");
	cs_pin = DSP1_CS; Init_Cs();
	default_download_IC_1();
	//SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF526, 2, dspLedOn);
    //pinclose(spi_cs);
	//pinwrite(dsp1_cs, HIGH);
	
	printf("\n// download DSP2 *********************************\n\n");
	cs_pin = DSP2_CS; Init_Cs();
	default_download_IC_2();	
    //SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF526, 2, dspLedOn);
    //pinclose(spi_cs);
	//pinwrite(dsp2_cs, HIGH);
	
	printf("\n// download DSP3 *********************************\n\n");
	//cs_pin = DSP3_CS; Init_Cs();
	//default_download_IC_3();
    
	
	//SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF526, 2, dspLedOn);
    //pinwrite(cs_pin, HIGH);
	//pinwrite(dsp3_cs, HIGH);
	
	//pinclose(spi_cs);
	printf("\n// download DSP4 *********************************\n\n");
	cs_pin = DSP4_CS; Init_Cs();
	default_download_IC_4();
    //SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF526, 2, dspLedOn);
    //pinclose(spi_cs);
	//pinwrite(dsp4_cs, HIGH);
	
	printf("\n// download DSP5 *********************************\n\n");
	cs_pin = DSP5_CS; Init_Cs();
	default_download_IC_5();
	//SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF526, 2, dspLedOn);
    //pinclose(spi_cs);
	//pinwrite(dsp5_cs, HIGH);
	
	printf("\n// download DSP6 *********************************\n\n");
	cs_pin = DSP6_CS; Init_Cs();
	default_download_IC_6();
	//SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF526, 2, dspLedOn);
    //pinclose(spi_cs);
	//pinwrite(dsp6_cs, HIGH);
	
	printf("\n// download DSP7 *********************************\n\n");
	cs_pin = DSP7_CS; Init_Cs();
	default_download_IC_7();
	//SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF526, 2, dspLedOn);
    //pinclose(spi_cs);
	//pinwrite(dsp7_cs, HIGH);
	
	printf("\n// download DSP8 *********************************\n\n");
	cs_pin = DSP8_CS; Init_Cs();
	default_download_IC_8();
	//SIGMA_WRITE_REGISTER_BLOCK(0x0, 0xF526, 2, dspLedOn);
    //pinclose(spi_cs);
	//pinwrite(dsp8_cs, HIGH);

	printf("\n// downloaded all *********************************\n\n");

/*
	// set all CS pins as inputs so MCU can control after boot
	cs_pin = DSP1_CS; pin_t spi_cs1 = pinopen(cs_pin, INPUT);
	cs_pin = DSP2_CS; pin_t spi_cs2 = pinopen(cs_pin, INPUT);
	cs_pin = DSP3_CS; pin_t spi_cs3 = pinopen(cs_pin, INPUT);
	cs_pin = DSP4_CS; pin_t spi_cs4 = pinopen(cs_pin, INPUT);
	cs_pin = DSP5_CS; pin_t spi_cs5 = pinopen(cs_pin, INPUT);
	cs_pin = DSP6_CS; pin_t spi_cs6 = pinopen(cs_pin, INPUT);
	cs_pin = DSP7_CS; pin_t spi_cs7 = pinopen(cs_pin, INPUT);
	cs_pin = DSP8_CS; pin_t spi_cs8 = pinopen(cs_pin, INPUT);
*/	
	
	//pinwrite(pi_mcu, HIGH); // MCU controls SPI CLK/MOSI/MISO


	printf("\n// finished *********************************\n\n");


	return ret;
}

void Init_Cs()
{
	pin_t spi_cs = pinopen(cs_pin, OUTPUT); pinwrite(spi_cs, HIGH); 
	sleep(.01); pinwrite(spi_cs, LOW); sleep(.01); pinwrite(spi_cs, HIGH);
	sleep(.01); pinwrite(spi_cs, LOW); sleep(.01); pinwrite(spi_cs, HIGH);
	sleep(.01); pinwrite(spi_cs, LOW); sleep(.01); pinwrite(spi_cs, HIGH);
}

pin_t pinopen(int pin, int mode)
{
        char*   pinfn = malloc(1024);
        char    dirfn[1024];
        FILE*   dir = NULL;
        FILE*   fp = fopen("/sys/class/gpio/export", "w");
        fprintf(fp, "%d", pin);
        fclose(fp);
        snprintf(dirfn, 1024, "/sys/class/gpio/gpio%d/direction", pin);
        snprintf(pinfn, 1024, "/sys/class/gpio/gpio%d/value", pin);
        while (dir == NULL) {
                dir = fopen(dirfn, "w");
        }
        if (mode == INPUT) {
                fprintf(dir, "in");
        } else {
                fprintf(dir, "out");
        }
        fclose(dir);
        return (pin_t) { pin, pinfn };
}

void pinclose(pin_t pin)
{
        FILE*   fp = fopen("/sys/class/gpio/unexport", "w");
        fprintf(fp, "%d", pin.pin);
        fclose(fp);
        free(pin.fn);
}

void pinwrite(pin_t pin, int value)
{
        FILE*   fp = fopen(pin.fn, "w");
        if (value == LOW) {
                fprintf(fp, "0");
        } else {
                fprintf(fp, "1");
        }
        fclose(fp);
}

int pinread(pin_t pin)
{
        char    buf[2];
        FILE*   fp = fopen(pin.fn, "r");
        size_t  read = fread(buf, 1, 2, fp);
        fclose(fp);
        if (read != 2) {
                return -1;
        } else {
                return (buf[0] == '1') ? HIGH : LOW;
        }
}

static int boot(uint8_t *boot_file, int boot_file_size)
{

//  enable cs pin and set low
    pin_t spi_cs = pinopen(cs_pin, OUTPUT);
    pinwrite(spi_cs, LOW);
    
	int ret = 0;
	int fd;

	//parse_opts(argc, argv);

	fd = open(device, O_RDWR);
	if (fd < 0)
		pabort("can't open device");

	ret = ioctl(fd, SPI_IOC_WR_MODE, &mode);
	if (ret == -1)
		pabort("can't set spi mode");

	ret = ioctl(fd, SPI_IOC_RD_MODE, &mode);
	if (ret == -1)
		pabort("can't get spi mode");

	ret = ioctl(fd, SPI_IOC_WR_BITS_PER_WORD, &bits);
	if (ret == -1)
		pabort("can't set bits per word");

	ret = ioctl(fd, SPI_IOC_RD_BITS_PER_WORD, &bits);
	if (ret == -1)
		pabort("can't get bits per word");

	ret = ioctl(fd, SPI_IOC_WR_MAX_SPEED_HZ, &speed);
	if (ret == -1)
		pabort("can't set max speed hz");

	ret = ioctl(fd, SPI_IOC_RD_MAX_SPEED_HZ, &speed);
	if (ret == -1)
		pabort("can't get max speed hz");

	printf("spi mode: 0x%x\n", mode);
	printf("bits per word: %d\n", bits);
	printf("max speed: %d Hz (%d KHz)\n", speed, speed/1000);

	if (input_tx && input_file)
		pabort("only one of -p and --input may be selected");

	if (input_tx)
		transfer_escaped_string(fd, input_tx);
	else if (input_file)
		transfer_file(fd, input_file);
	else
		transfer(fd, boot_file, default_rx, boot_file_size);

	close(fd);

	// set hi and disable cs pin
    pinwrite(spi_cs, HIGH);
    //pinclose(spi_cs);

	//return boot(17, default_tx);
	return ret;
}
