/* main.c -- H1S1 on the DSP card rev D (U7 = STM32G0B1RET6). S174.
 *
 * The rev C H1S1 (MW/D24/FW/H1S1, STM32U575) ported to the rev D card's
 * G0B1, from invirco/dspcard review/stage2b-u7-pinmap.md (stage 3d) and
 * review/l11-report.md. The panel-bus protocol is rev C's (matrix.cs); the
 * pins, the clock and the option bytes are this part's.
 */
#include "main.h"

#include "matrix.cs"

UART_HandleTypeDef huart1;

void SystemClock_Config(void);
static void BootSelFromPin(void);
static void MX_GPIO_Init(void);
static void MX_USART1_UART_Init(void);

int main(void)
{
    HAL_Init();                   /* HAL_MspInit: UCPD dead-battery strobes */
    SystemClock_Config();
    BootSelFromPin();             /* may reset the MCU once, on first run */
    MX_GPIO_Init();
    MX_USART1_UART_Init();
    __HAL_UART_ENABLE_IT(&huart1, UART_IT_RXNE);

    MainInit();
    while (1)
    {
        MainLoop();
    }
}

/* BOOT0 FROM THE PIN (S173-6). MH1 updates this MCU the rev C way: S1 high
 * on BOOT0, S0 pulses NRST, the ROM bootloader answers on USART1. A G0B1
 * leaves the factory with nBOOT_SEL = 1, which takes BOOT0 from the nBOOT0
 * option bit and IGNORES the pin. A blank part still reaches the loader by
 * its empty check, so the first load works -- and every load after it
 * would not. So the image clears nBOOT_SEL itself the first time it runs
 * (nBOOT1 = 1 alongside, so BOOT0 high means the system memory, never
 * SRAM). Read first: once the bit is right this is a single register read
 * and nothing is ever written again. The USER-only HAL path rewrites the
 * register with the RDP byte it read, so read protection is unchanged.
 * Programming ends in an option-byte reload, which is a system reset. */
static void BootSelFromPin(void)
{
    FLASH_OBProgramInitTypeDef ob = {0};

    if (((FLASH->OPTR & FLASH_OPTR_nBOOT_SEL) == 0u)
        && ((FLASH->OPTR & FLASH_OPTR_nBOOT1) != 0u))
    {
        return;
    }
    ob.OptionType = OPTIONBYTE_USER;
    ob.USERType = OB_USER_nBOOT_SEL | OB_USER_nBOOT1;
    ob.USERConfig = OB_BOOT0_FROM_PIN | OB_BOOT1_SYSTEM;
    if (HAL_FLASH_Unlock() == HAL_OK && HAL_FLASH_OB_Unlock() == HAL_OK)
    {
        if (HAL_FLASHEx_OBProgram(&ob) == HAL_OK)
        {
            (void)HAL_FLASH_OB_Launch();   /* resets; returns only on failure */
        }
    }
    (void)HAL_FLASH_OB_Lock();
    (void)HAL_FLASH_Lock();
}

/* HSI16 -> PLL -> 64 MHz SYSCLK, the G0's ceiling (the rev C U575 ran
 * 160 MHz; nothing in the bus protocol is timed off the core clock). */
void SystemClock_Config(void)
{
    RCC_OscInitTypeDef RCC_OscInitStruct = {0};
    RCC_ClkInitTypeDef RCC_ClkInitStruct = {0};

    HAL_PWREx_ControlVoltageScaling(PWR_REGULATOR_VOLTAGE_SCALE1);

    RCC_OscInitStruct.OscillatorType = RCC_OSCILLATORTYPE_HSI;
    RCC_OscInitStruct.HSIState = RCC_HSI_ON;
    RCC_OscInitStruct.HSIDiv = RCC_HSI_DIV1;
    RCC_OscInitStruct.HSICalibrationValue = RCC_HSICALIBRATION_DEFAULT;
    RCC_OscInitStruct.PLL.PLLState = RCC_PLL_ON;
    RCC_OscInitStruct.PLL.PLLSource = RCC_PLLSOURCE_HSI;
    RCC_OscInitStruct.PLL.PLLM = RCC_PLLM_DIV1;
    RCC_OscInitStruct.PLL.PLLN = 8;
    RCC_OscInitStruct.PLL.PLLP = RCC_PLLP_DIV2;
    RCC_OscInitStruct.PLL.PLLQ = RCC_PLLQ_DIV2;
    RCC_OscInitStruct.PLL.PLLR = RCC_PLLR_DIV2;
    if (HAL_RCC_OscConfig(&RCC_OscInitStruct) != HAL_OK)
    {
        Error_Handler();
    }

    RCC_ClkInitStruct.ClockType = RCC_CLOCKTYPE_HCLK | RCC_CLOCKTYPE_SYSCLK
                                | RCC_CLOCKTYPE_PCLK1;
    RCC_ClkInitStruct.SYSCLKSource = RCC_SYSCLKSOURCE_PLLCLK;
    RCC_ClkInitStruct.AHBCLKDivider = RCC_SYSCLK_DIV1;
    RCC_ClkInitStruct.APB1CLKDivider = RCC_HCLK_DIV1;
    if (HAL_RCC_ClockConfig(&RCC_ClkInitStruct, FLASH_LATENCY_2) != HAL_OK)
    {
        Error_Handler();
    }
}

/* USART1, the panel bus: 115200 8N1, as rev C. */
static void MX_USART1_UART_Init(void)
{
    huart1.Instance = USART1;
    huart1.Init.BaudRate = 115200;
    huart1.Init.WordLength = UART_WORDLENGTH_8B;
    huart1.Init.StopBits = UART_STOPBITS_1;
    huart1.Init.Parity = UART_PARITY_NONE;
    huart1.Init.Mode = UART_MODE_TX_RX;
    huart1.Init.HwFlowCtl = UART_HWCONTROL_NONE;
    huart1.Init.OverSampling = UART_OVERSAMPLING_16;
    huart1.Init.OneBitSampling = UART_ONE_BIT_SAMPLE_DISABLE;
    huart1.Init.ClockPrescaler = UART_PRESCALER_DIV1;
    huart1.AdvancedInit.AdvFeatureInit = UART_ADVFEATURE_NO_INIT;
    if (HAL_UART_Init(&huart1) != HAL_OK)
    {
        Error_Handler();
    }
    if (HAL_UARTEx_SetTxFifoThreshold(&huart1, UART_TXFIFO_THRESHOLD_1_8) != HAL_OK)
    {
        Error_Handler();
    }
    if (HAL_UARTEx_SetRxFifoThreshold(&huart1, UART_RXFIFO_THRESHOLD_1_8) != HAL_OK)
    {
        Error_Handler();
    }
    if (HAL_UARTEx_DisableFifoMode(&huart1) != HAL_OK)
    {
        Error_Handler();
    }
}

static void MX_GPIO_Init(void)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};

    __HAL_RCC_GPIOA_CLK_ENABLE();
    __HAL_RCC_GPIOB_CLK_ENABLE();
    __HAL_RCC_GPIOC_CLK_ENABLE();
    __HAL_RCC_GPIOF_CLK_ENABLE();

    /* Output levels before the pins become outputs. RST_C and RST_O start
     * LOW (held in reset until MainInit's pulse releases them), as rev C
     * starts RST_C; the LED on, as rev C; S2 low, as rev C (MainInit then
     * raises it). */
    HAL_GPIO_WritePin(BLINK_GPIO_Port, BLINK_Pin, GPIO_PIN_SET);
    HAL_GPIO_WritePin(RST_C_GPIO_Port, RST_C_Pin | RST_O_Pin, GPIO_PIN_RESET);
    HAL_GPIO_WritePin(S2_GPIO_Port, S2_Pin, GPIO_PIN_RESET);

    /* ALL the CM4's chip selects and both RDY lines are INPUTS, never
     * driven, exactly as rev C (its MX_GPIO_Init_2 note). On rev D CS6 is
     * off U7 altogether. */
    GPIO_InitStruct.Pin = CS5_Pin | CS2_Pin | CS7_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_INPUT;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    HAL_GPIO_Init(GPIOC, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = CS8_Pin;
    HAL_GPIO_Init(CS8_GPIO_Port, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = CS1_Pin | CS4_Pin | CS3_Pin | BUSY_Pin | S3_Pin;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    GPIO_InitStruct.Pin = BLINK_Pin | S2_Pin;
    GPIO_InitStruct.Mode = GPIO_MODE_OUTPUT_PP;
    GPIO_InitStruct.Pull = GPIO_NOPULL;
    GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
    HAL_GPIO_Init(GPIOB, &GPIO_InitStruct);

    /* RST_C (PA11) and RST_O (PA12), push-pull. Pins 43/44 are PA11/PA12
     * only while SYSCFG PA11_RMP / PA12_RMP stay clear (their reset value;
     * nothing here sets them) -- set, they would carry PA9/PA10. */
    GPIO_InitStruct.Pin = RST_C_Pin | RST_O_Pin;
    HAL_GPIO_Init(RST_C_GPIO_Port, &GPIO_InitStruct);

    /* Not configured, and so left at reset: PA13 (SWDIO, on the open-drain
     * !RST_D net -- U7 never drives RST_D, as rev C), PA14 (SWCLK/BOOT0),
     * SPI1 PB3/PB4/PB5, !CS_L PD0, LOGIC_P23..25 PA8/PC9/PC8, the spare
     * UARTs, and every PSU-monitor pin (removed in stage 3d). REV_ID0..2
     * PC1..PC3 are set up by dsp_card_rev_read() at MainInit. */
}

void Error_Handler(void)
{
    __disable_irq();
    while (1)
    {
    }
}

#ifdef USE_FULL_ASSERT
void assert_failed(uint8_t *file, uint32_t line)
{
    (void)file;
    (void)line;
}
#endif
