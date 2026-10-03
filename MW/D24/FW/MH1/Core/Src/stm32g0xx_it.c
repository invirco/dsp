/* USER CODE BEGIN Header */
/**
 ******************************************************************************
 * @file    stm32g0xx_it.c
 * @brief   Interrupt Service Routines.
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

/* Includes ------------------------------------------------------------------*/
#include "main.h"
#include "stm32g0xx_it.h"
/* Private includes ----------------------------------------------------------*/
/* USER CODE BEGIN Includes */
#include "Project.h"
/* USER CODE END Includes */

/* Private typedef -----------------------------------------------------------*/
/* USER CODE BEGIN TD */

/* USER CODE END TD */

/* Private define ------------------------------------------------------------*/
/* USER CODE BEGIN PD */

/* USER CODE END PD */

/* Private macro -------------------------------------------------------------*/
/* USER CODE BEGIN PM */

/* USER CODE END PM */

/* Private variables ---------------------------------------------------------*/
/* USER CODE BEGIN PV */
extern char blink, blinkReady, debugFlag, hostMessageReady, myChar,
		sMessageReady;
extern char hostMessage[100], sMessage[100];
/* USER CODE END PV */

/* Private function prototypes -----------------------------------------------*/
/* USER CODE BEGIN PFP */

extern char UART1_Read(void);
extern char UART2_Read(void);
extern void DimI(void);
extern void DimD(void);

/* USER CODE END PFP */

/* Private user code ---------------------------------------------------------*/
/* USER CODE BEGIN 0 */

/* USER CODE END 0 */

/* External variables --------------------------------------------------------*/
extern TIM_HandleTypeDef htim3;
extern UART_HandleTypeDef huart1;
extern UART_HandleTypeDef huart2;
/* USER CODE BEGIN EV */

/* USER CODE END EV */

/******************************************************************************/
/*           Cortex-M0+ Processor Interruption and Exception Handlers          */
/******************************************************************************/
/**
 * @brief This function handles Non maskable interrupt.
 */
void NMI_Handler(void) {
	/* USER CODE BEGIN NonMaskableInt_IRQn 0 */

	/* USER CODE END NonMaskableInt_IRQn 0 */
	/* USER CODE BEGIN NonMaskableInt_IRQn 1 */
	while (1) {
	}
	/* USER CODE END NonMaskableInt_IRQn 1 */
}

/**
 * @brief This function handles Hard fault interrupt.
 */
void HardFault_Handler(void) {
	/* USER CODE BEGIN HardFault_IRQn 0 */

	/* USER CODE END HardFault_IRQn 0 */
	while (1) {
		/* USER CODE BEGIN W1_HardFault_IRQn 0 */
		/* USER CODE END W1_HardFault_IRQn 0 */
	}
}

/**
 * @brief This function handles System service call via SWI instruction.
 */
void SVC_Handler(void) {
	/* USER CODE BEGIN SVC_IRQn 0 */

	/* USER CODE END SVC_IRQn 0 */
	/* USER CODE BEGIN SVC_IRQn 1 */

	/* USER CODE END SVC_IRQn 1 */
}

/**
 * @brief This function handles Pendable request for system service.
 */
void PendSV_Handler(void) {
	/* USER CODE BEGIN PendSV_IRQn 0 */

	/* USER CODE END PendSV_IRQn 0 */
	/* USER CODE BEGIN PendSV_IRQn 1 */

	/* USER CODE END PendSV_IRQn 1 */
}

/**
 * @brief This function handles System tick timer.
 */
void SysTick_Handler(void) {
	/* USER CODE BEGIN SysTick_IRQn 0 */

	/* USER CODE END SysTick_IRQn 0 */
	HAL_IncTick();
	/* USER CODE BEGIN SysTick_IRQn 1 */

	/* USER CODE END SysTick_IRQn 1 */
}

/******************************************************************************/
/* STM32G0xx Peripheral Interrupt Handlers                                    */
/* Add here the Interrupt Handlers for the used peripherals.                  */
/* For the available peripheral interrupt handler names,                      */
/* please refer to the startup file (startup_stm32g0xx.s).                    */
/******************************************************************************/

/**
 * @brief This function handles TIM3 global interrupt.
 */
void TIM3_IRQHandler(void) {
	/* USER CODE BEGIN TIM3_IRQn 0 */
	blink++;
	blink &= 0x7;
	blinkReady = 1;
	/* USER CODE END TIM3_IRQn 0 */
	HAL_TIM_IRQHandler(&htim3);
	/* USER CODE BEGIN TIM3_IRQn 1 */

	/* USER CODE END TIM3_IRQn 1 */
}

/**
 * @brief This function handles USART1 global interrupt / USART1 wake-up interrupt through EXTI line 25.
 */
void USART1_IRQHandler(void) {
	/* USER CODE BEGIN USART1_IRQn 0 */
	// 2026-08-19 rev C bring-up fix #2 (host-side twin of the USART2 fix):
	// (a) the blocking UART1_Read() wedges on an error-flag IRQ entry
	//     (SysTick frozen in handler → 100ms timeout never expires);
	// (b) worse: HAL_UART_IRQHandler's error path DISABLES RXNEIE on a
	//     framing/overrun error — the CM4 glitches GPIO14 during ITS boot,
	//     which one-way-deafened MH1 to the host (bench-proven 2026-08-19
	//     after a CM4 reboot: RXNE+ORE set, ISR never consuming).
	// Non-blocking drain + explicit error clear BEFORE the HAL handler so
	// it never sees an error to "handle".
	static char hostMessagePtr = 0;
	while (USART1->ISR & USART_ISR_RXNE_RXFNE) {
	char myChar = (char) USART1->RDR;
	hostMessage[(int) hostMessagePtr] = myChar;
	hostMessagePtr++;
	if (hostMessagePtr >= (char) sizeof(hostMessage))
		hostMessagePtr = 0; // guard: garbage without newline must not overrun

	switch (myChar) {
	case '\n':
		hostMessagePtr = 0;
		hostMessageReady = 1;
		break;
	case P_DIMI:
		DimI();
		//Delay_us(DELAY_US);
		break;
	case P_DIMD:
		DimD();
		//Delay_us(DELAY_US);
		break;
	case '^':
		debugFlag = 1;
		break;
	case S_RESET:
		HAL_NVIC_SystemReset();
		break;
	default:
		break;
	}

	//if (myChar == S_RESET) {
	//	HAL_NVIC_SystemReset();
	//}
	//else if (myChar == 0x0a) {
	//	hostMessagePtr = 0;
	//	hostMessageReady = 1;
//}
	//else if (myChar == '^') {
	//	debugFlag = 1;
	//}

// change to switch case and add extra functions below
	/*
	 case ID:
	 GPIO_Config(SBSB_DIR, _GPIO_CFG_DIGITAL_OUTPUT | _GPIO_CFG_OTYPE_OD | _GPIO_CFG_PULL_UP); SBSB_O = 0; // set busy bus
	 Delay_us(DELAY_US);
	 if (sDataReady) {sDataReady = 0; sDataSend = 1;} // if S has data ready, signal S to broadcast data
	 else {GPIO_Config( SBSB_DIR, _GPIO_CFG_DIGITAL_INPUT | _GPIO_CFG_PULL_UP);} // ***TEST*** // clear busy bus
	 Delay_us(DELAY_US); // ***TEST***
	 break; // clear busy
	 case P_DIMI: DimI(); Delay_us(DELAY_US); break; // led DIM inc
	 case P_DIMD: DimD(); Delay_us(DELAY_US); break; // led DIM dec
	 */

	} // while RXNE (2026-08-19 non-blocking drain)
	USART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF
			| USART_ICR_PECF;
	/* USER CODE END USART1_IRQn 0 */
	HAL_UART_IRQHandler(&huart1);
	/* USER CODE BEGIN USART1_IRQn 1 */

	/* USER CODE END USART1_IRQn 1 */
}

/**
 * @brief This function handles USART2 global interrupt / USART2 wake-up interrupt through EXTI line 26.
 */
void USART2_IRQHandler(void) {
	/* USER CODE BEGIN USART2_IRQn 0 */
	// 2026-08-19 rev C bring-up fix: the original blocking UART2_Read() here
	// wedges permanently when this IRQ fires with no RXNE pending (ORE from a
	// panel announcement burst at StartAllSlaves): HAL_UART_Receive spins on
	// HAL_GetTick, and SysTick (lowest priority) cannot advance inside this
	// handler, so the 100ms timeout never expires and the MCU goes deaf.
	// Non-blocking register read instead; error flags cleared explicitly.
	// Original (rev A behaviour, kept for reference):
	//	static char sMessagePtr = 0;
	//	char myChar = UART2_Read();
	//	sMessage[sMessagePtr] = myChar;
	//	sMessagePtr++;
	//	if (myChar == 0x0a) {
	//		sMessagePtr = 0;
	//		sMessageReady = 1;
	//	}
	static char sMessagePtr = 0;
	while (USART2->ISR & USART_ISR_RXNE_RXFNE) {
		char myChar = (char) USART2->RDR;
		if (sMessagePtr >= (char) sizeof(sMessage))
			sMessagePtr = 0; // guard: garbage without newline must not overrun
		sMessage[(int) sMessagePtr] = myChar;
		sMessagePtr++;
		if (myChar == 0x0a) {
			sMessagePtr = 0;
			sMessageReady = 1;
		}
	}
	USART2->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF
			| USART_ICR_PECF;
	/* USER CODE END USART2_IRQn 0 */
	HAL_UART_IRQHandler(&huart2);
	/* USER CODE BEGIN USART2_IRQn 1 */

	/* USER CODE END USART2_IRQn 1 */
}

/* USER CODE BEGIN 1 */
/* USER CODE END 1 */
/************************ (C) COPYRIGHT STMicroelectronics *****END OF FILE****/
