/* stm32g0xx_hal_msp.c -- MSP init, H1S1 rev D (STM32G0B1RET6). S174. */
#include "main.h"

void HAL_MspInit(void)
{
    __HAL_RCC_SYSCFG_CLK_ENABLE();
    __HAL_RCC_PWR_CLK_ENABLE();

    /* UCPD dead-battery pull-downs OFF, first thing. Until the strobe bits
     * are set, a G0B1 whose DBCC pins read high puts the UCPD Rd (5.1K to
     * GND) on the CC pads: UCPD1 PA8 = LOGIC_P23 / SWD_EN0, and UCPD2 PD0 /
     * PD2 = !CS_L / STRX1 (stage2b pin map, PA8 note). None of them is a
     * USB-C port here; a 5.1K pull-down on a chip select or an enable is a
     * fault. Both ports, always. */
    HAL_SYSCFG_StrobeDBattpinsConfig(SYSCFG_UCPD1_STROBE | SYSCFG_UCPD2_STROBE);
}

void HAL_UART_MspInit(UART_HandleTypeDef *huart)
{
    GPIO_InitTypeDef GPIO_InitStruct = {0};
    RCC_PeriphCLKInitTypeDef PeriphClkInit = {0};
    if (huart->Instance == USART1)
    {
        PeriphClkInit.PeriphClockSelection = RCC_PERIPHCLK_USART1;
        PeriphClkInit.Usart1ClockSelection = RCC_USART1CLKSOURCE_PCLK1;
        if (HAL_RCCEx_PeriphCLKConfig(&PeriphClkInit) != HAL_OK)
        {
            Error_Handler();
        }
        __HAL_RCC_USART1_CLK_ENABLE();
        __HAL_RCC_GPIOA_CLK_ENABLE();
        /* PA9 USART1_TX, PA10 USART1_RX -- the ROM bootloader's port too
         * (AN2606, G0B1). TX open-drain with pull-up, exactly as rev C:
         * the panel bus is multi-drop and every MCU on it transmits. */
        GPIO_InitStruct.Pin = GPIO_PIN_9;
        GPIO_InitStruct.Mode = GPIO_MODE_AF_OD;
        GPIO_InitStruct.Pull = GPIO_PULLUP;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
        GPIO_InitStruct.Alternate = GPIO_AF1_USART1;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

        GPIO_InitStruct.Pin = GPIO_PIN_10;
        GPIO_InitStruct.Mode = GPIO_MODE_AF_PP;
        GPIO_InitStruct.Pull = GPIO_NOPULL;
        GPIO_InitStruct.Speed = GPIO_SPEED_FREQ_LOW;
        GPIO_InitStruct.Alternate = GPIO_AF1_USART1;
        HAL_GPIO_Init(GPIOA, &GPIO_InitStruct);

        HAL_NVIC_SetPriority(USART1_IRQn, 0, 0);
        HAL_NVIC_EnableIRQ(USART1_IRQn);
    }
}
