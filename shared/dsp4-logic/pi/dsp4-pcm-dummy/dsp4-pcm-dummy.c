// SPDX-License-Identifier: GPL-2.0
/*
 * dsp4-pcm-dummy — a codec-side DAI declaration, and nothing else.
 *
 * The DSP4 bench needs the CM4 to be an I2S SLAVE in BOTH directions on
 * ONE dai-link: two links sharing one bcm2835-i2s block re-program each
 * other's framing, which is the scramble the 2026-09-08 rung-2 work hit.
 * simple-audio-card takes the intersection of what the CPU and CODEC DAIs
 * declare, so a single link needs a codec that declares both directions,
 * and the Pi tree has none that also fits this link:
 *
 *   linux,spdif-dit     playback only
 *   linux,spdif-dir     capture only
 *   asahi-kasei,ak4554  both, S16_LE only  (measured on the bench)
 *   google,voicehat     both, S32_LE, 48 kHz ONLY (measured: the capture
 *                       overruns by ~1.6 s and a known word comes back as
 *                       a constant unrelated to what was played)
 *
 * The link is 2 slots x 32 bits at 192 kHz — LOGIC regroups four Pi
 * frames into one 8-slot 48 kHz DSP frame (shared/dsp4-logic/slot-map.csv,
 * lane A_I6) — so 192 kHz and S32_LE are both requirements, not
 * preferences.
 *
 * This driver has no registers, no control bus, no clocks and no GPIOs.
 * It exists so that the DT has something to point `sound-dai` at.
 */
#include <linux/module.h>
#include <linux/of.h>
#include <linux/platform_device.h>
#include <sound/soc.h>

static struct snd_soc_dai_driver dsp4_dummy_dai = {
	.name = "dsp4-dummy-hifi",
	.playback = {
		.stream_name	= "Playback",
		.channels_min	= 1,
		.channels_max	= 8,
		.rates		= SNDRV_PCM_RATE_8000_192000,
		.formats	= SNDRV_PCM_FMTBIT_S32_LE,
	},
	.capture = {
		.stream_name	= "Capture",
		.channels_min	= 1,
		.channels_max	= 8,
		.rates		= SNDRV_PCM_RATE_8000_192000,
		.formats	= SNDRV_PCM_FMTBIT_S32_LE,
	},
	/* One clock domain, one rate: the CPLD masters both directions from
	 * the same pcm_fs, so playback and capture can never differ. */
	.symmetric_rate = 1,
	.symmetric_channels = 1,
	.symmetric_sample_bits = 1,
};

static const struct snd_soc_component_driver dsp4_dummy_component = {
	.idle_bias_on		= 1,
	.use_pmdown_time	= 1,
	.endianness		= 1,
};

static int dsp4_dummy_probe(struct platform_device *pdev)
{
	return devm_snd_soc_register_component(&pdev->dev,
					       &dsp4_dummy_component,
					       &dsp4_dummy_dai, 1);
}

static const struct of_device_id dsp4_dummy_of_match[] = {
	{ .compatible = "invirco,dsp4-pcm-dummy", },
	{ }
};
MODULE_DEVICE_TABLE(of, dsp4_dummy_of_match);

static struct platform_driver dsp4_dummy_driver = {
	.probe = dsp4_dummy_probe,
	.driver = {
		.name		= "dsp4-pcm-dummy",
		.of_match_table	= dsp4_dummy_of_match,
	},
};
module_platform_driver(dsp4_dummy_driver);

MODULE_DESCRIPTION("DSP4 bidirectional I2S dummy codec (bench measurement channel)");
MODULE_AUTHOR("invirco");
MODULE_LICENSE("GPL v2");
