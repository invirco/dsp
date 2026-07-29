rem copy support files to RPi server, compile dsp_boot, copy to proto and reboot

rem set RPi4 server address
set ipAdd=192.168.1.143

rem set brand_product folder path
set brandProduct=MW/D24

rem set proto ip
set protoIpAdd=192.168.1.160

rem copy dsp_boot files to Rpi server /home/app/dsp_boot_source folder
scp "C:/dropbox/_mx/%brandProduct%/DSP/dsp_boot.c" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_1.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_1_PARAM.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_2.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_2_PARAM.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_3.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_3_PARAM.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_4.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_4_PARAM.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_5.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_5_PARAM.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_6.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_6_PARAM.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_7.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_7_PARAM.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_8.h" app@%ipAdd%:~/dsp_boot_source/
scp "C:/dropbox/_mx/%brandProduct%/DSP/DSP_Export/DSP_IC_8_PARAM.h" app@%ipAdd%:~/dsp_boot_source/

rem compile dsp_boot.c
ssh -T app@%ipAdd% "gcc /home/app/dsp_boot_source/dsp_boot.c -o /home/app/dsp_boot_source/dsp_boot -l bcm2835"
rem mark dsp_boot as executable
ssh -T app@%ipAdd% "sudo chmod +x /home/app/dsp_boot_source/dsp_boot"

rem copy compiled file dsp_boot back to source folder
scp app@%ipAdd%:~/dsp_boot_source/dsp_boot "C:/dropbox/_mx/%brandProduct%/DSP/"

rem copy dsp_boot to proto and reset
scp app@%ipAdd%:~/dsp_boot_source/dsp_boot app@%protoIpAdd%:~/dsp_boot
ssh -T app@%protoIpAdd% "sudo reboot"

pause