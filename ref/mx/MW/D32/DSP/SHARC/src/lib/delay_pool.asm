/*======================================================================
 * delay_pool.asm — Shared long-delay storage for assignable input slots
 *
 * Eight 250 ms mono delay slots at 48 kHz. These are intended to be
 * assigned uniquely by the MCU using each channel DELAY node's pool_slot
 * parameter. A negative pool_slot value selects the node-local short buffer.
 *======================================================================*/

.section/dm seg_delay;
.global _dly_pool_buf_00;
.var _dly_pool_buf_00[12000];
.global _dly_pool_buf_01;
.var _dly_pool_buf_01[12000];
.global _dly_pool_buf_02;
.var _dly_pool_buf_02[12000];
.global _dly_pool_buf_03;
.var _dly_pool_buf_03[12000];
.global _dly_pool_buf_04;
.var _dly_pool_buf_04[12000];
.global _dly_pool_buf_05;
.var _dly_pool_buf_05[12000];
.global _dly_pool_buf_06;
.var _dly_pool_buf_06[12000];
.global _dly_pool_buf_07;
.var _dly_pool_buf_07[12000];

.section/dm seg_dmda;
.global _dly_pool_wptr_00;
.var _dly_pool_wptr_00 = 0;
.global _dly_pool_wptr_01;
.var _dly_pool_wptr_01 = 0;
.global _dly_pool_wptr_02;
.var _dly_pool_wptr_02 = 0;
.global _dly_pool_wptr_03;
.var _dly_pool_wptr_03 = 0;
.global _dly_pool_wptr_04;
.var _dly_pool_wptr_04 = 0;
.global _dly_pool_wptr_05;
.var _dly_pool_wptr_05 = 0;
.global _dly_pool_wptr_06;
.var _dly_pool_wptr_06 = 0;
.global _dly_pool_wptr_07;
.var _dly_pool_wptr_07 = 0;
