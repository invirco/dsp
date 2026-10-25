/* stm32g0xx_it.c -- interrupt handlers, H1S1 rev D (STM32G0B1RET6). S174. */
#include "main.h"
#include "stm32g0xx_it.h"

extern UART_HandleTypeDef huart1;
extern void Uart1_Rx(char c);

void NMI_Handler(void) { while (1) { } }
void HardFault_Handler(void) { while (1) { } }
void SVC_Handler(void) { }
void PendSV_Handler(void) { }
void SysTick_Handler(void) { HAL_IncTick(); }

/* The panel bus, USART1 on PA9/PA10 (MH1). Rev C's handler reads one byte
 * with a BLOCKING HAL_UART_Receive and then lets HAL_UART_IRQHandler run.
 * MH1 found both traps on its own USART1 at rev C bring-up (2026-08-19,
 * MW/D24/FW/MH1 stm32g0xx_it.c): an error-flag entry with no byte wedges
 * the blocking read (SysTick is frozen under this handler, so its 100 ms
 * timeout never expires), and the HAL's error path DISABLES RXNEIE on a
 * framing or overrun error, deafening the MCU for good. So here: drain the
 * receive FIFO without blocking, clear the error flags, THEN the HAL
 * handler, which then has nothing to "handle". The bytes reach the same
 * per-character vector table as rev C (matrix.cs). */
void USART1_IRQHandler(void)
{
    while (USART1->ISR & USART_ISR_RXNE_RXFNE)
    {
        Uart1_Rx((char)USART1->RDR);
    }
    USART1->ICR = USART_ICR_ORECF | USART_ICR_FECF | USART_ICR_NECF
                | USART_ICR_PECF;
    HAL_UART_IRQHandler(&huart1);
}
