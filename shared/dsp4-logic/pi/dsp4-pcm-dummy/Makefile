# Out-of-tree build for the DSP4 bench measurement channel.
#   make            build against the running kernel
#   sudo make install   install + depmod (bench only)
obj-m += dsp4-pcm-dummy.o

KDIR ?= /lib/modules/$(shell uname -r)/build

all:
	$(MAKE) -C $(KDIR) M=$(PWD) modules

# NOT `install: all` -- rebuilding under sudo re-runs the kernel build as
# root in a tree owned by the build user and fails. Build first, then
# install.
install:
	install -D -m 644 dsp4-pcm-dummy.ko \
	  /lib/modules/$(shell uname -r)/kernel/sound/soc/codecs/dsp4-pcm-dummy.ko
	depmod -a

clean:
	$(MAKE) -C $(KDIR) M=$(PWD) clean
