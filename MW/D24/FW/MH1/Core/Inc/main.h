/* USER CODE BEGIN Header */
/**
 ******************************************************************************
 * @file           : main.h
 * @brief          : Header for main.c file.
 *                   This file contains the common defines of the application.
 ******************************************************************************
 * @attention
 *
 * <h2><center>&copy; Copyright (c) 2021 STMicroelectronics.
 * All rights reserved.</center></h2>
 *
 * This software component is licensed by ST under BSD 3-Clause license,
 * the "License"; You may not use this file except in compliance with the
 * License. You may obtain a copy of the License at:
 *                        opensource.org/licenses/BSD-3-Clause
 *
 ******************************************************************************
 */
/* USER CODE END Header */

/* Define to prevent recursive inclusion -------------------------------------*/
#ifndef __MAIN_H
#define __MAIN_H

#ifdef __cplusplus
extern "C" {
#endif

/* Includes ------------------------------------------------------------------*/
#include "stm32g0xx_hal.h"

/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "Project.h"
#include <math.h>
#include <stdio.h>

/* USER CODE END Includes */

/* Exported types ------------------------------------------------------------*/
/* USER CODE BEGIN ET */

/* USER CODE END ET */

/* Exported constants --------------------------------------------------------*/
/* USER CODE BEGIN EC */
enum {
	P_RES, P_INIT, P_MAIN, P_DIMI, P_DIMD, P_SER
};

/* USER CODE END EC */

/* Exported macro ------------------------------------------------------------*/
/* USER CODE BEGIN EM */

/* USER CODE END EM */

void HAL_TIM_MspPostInit(TIM_HandleTypeDef *htim);

/* Exported functions prototypes ---------------------------------------------*/
void Error_Handler(void);

/* USER CODE BEGIN EFP */

/* USER CODE END EFP */

/* Private defines -----------------------------------------------------------*/
#define BUSY_Pin GPIO_PIN_13
#define BUSY_GPIO_Port GPIOC
#define S0_Pin GPIO_PIN_14
#define S0_GPIO_Port GPIOC
#define S1_Pin GPIO_PIN_15
#define S1_GPIO_Port GPIOC
#define S2_Pin GPIO_PIN_0
#define S2_GPIO_Port GPIOF
#define S3_Pin GPIO_PIN_1
#define S3_GPIO_Port GPIOF
#define S4_Pin GPIO_PIN_0
#define S4_GPIO_Port GPIOA
#define S5_Pin GPIO_PIN_1
#define S5_GPIO_Port GPIOA
#define S6_Pin GPIO_PIN_4
#define S6_GPIO_Port GPIOA
#define S7_Pin GPIO_PIN_5
#define S7_GPIO_Port GPIOA
#define S8_Pin GPIO_PIN_6
#define S8_GPIO_Port GPIOA
#define S9_Pin GPIO_PIN_7
#define S9_GPIO_Port GPIOA
#define S10_Pin GPIO_PIN_0
#define S10_GPIO_Port GPIOB
#define S11_Pin GPIO_PIN_1
#define S11_GPIO_Port GPIOB
#define S12_Pin GPIO_PIN_2
#define S12_GPIO_Port GPIOB
#define S13_Pin GPIO_PIN_10
#define S13_GPIO_Port GPIOB
#define S14_Pin GPIO_PIN_11
#define S14_GPIO_Port GPIOB
#define S15_Pin GPIO_PIN_12
#define S15_GPIO_Port GPIOB
#define S16_Pin GPIO_PIN_13
#define S16_GPIO_Port GPIOB
#define S17_Pin GPIO_PIN_14
#define S17_GPIO_Port GPIOB
#define S18_Pin GPIO_PIN_15
#define S18_GPIO_Port GPIOB
#define S19_Pin GPIO_PIN_8
#define S19_GPIO_Port GPIOA
#define S20_Pin GPIO_PIN_6
#define S20_GPIO_Port GPIOC
#define S21_Pin GPIO_PIN_7
#define S21_GPIO_Port GPIOC
#define S22_Pin GPIO_PIN_11
#define S22_GPIO_Port GPIOA
#define S23_Pin GPIO_PIN_12
#define S23_GPIO_Port GPIOA
#define S24_Pin GPIO_PIN_15
#define S24_GPIO_Port GPIOA
#define S25_Pin GPIO_PIN_0
#define S25_GPIO_Port GPIOD
#define S26_Pin GPIO_PIN_1
#define S26_GPIO_Port GPIOD
#define S27_Pin GPIO_PIN_2
#define S27_GPIO_Port GPIOD
#define S28_Pin GPIO_PIN_3
#define S28_GPIO_Port GPIOD
#define S29_Pin GPIO_PIN_3
#define S29_GPIO_Port GPIOB
#define S30_Pin GPIO_PIN_4
#define S30_GPIO_Port GPIOB
#define S31_Pin GPIO_PIN_5
#define S31_GPIO_Port GPIOB
#define S2S_Pin GPIO_PIN_7
#define S2S_GPIO_Port GPIOB
#define DIM_Pin GPIO_PIN_8
#define DIM_GPIO_Port GPIOB
#define BLINK_Pin GPIO_PIN_9
#define BLINK_GPIO_Port GPIOB
/* USER CODE BEGIN Private defines */
#define M_FW_REV    "241022" // master firmware revision
// rev 1.000 first rev
// rev 1.001 added S_FILL_START and S_FILL_STOP instructions for fast loading matrix
// rev 1.002 modified handshaking to optimize fast load matrix
// rev 1.003 disable interrupts during matrix fill
// rev 1.004 modify status LED to also work with DSP2
// rev 2.000 new MH code for DSP3, created with STM32CubeIDE
// rev 3.000 new MH1 working code
// rev 3.001 MH1, hold all MCUs in reset mode after power up.
#define TIMEOUT100MS 0x7fff0 //0x7530 // response timeout counter in clock cycles, might need adjusting if clocks change
#define TIMEOUTR    0x07ffffff0 //0x00ffffff // response timeout counter in clock cycles, might need adjusting if clocks change

/* USER CODE END Private defines */

#ifdef __cplusplus
}
#endif

#endif /* __MAIN_H */

/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/
