const SPEED_PERCENTILE = 0.95;
const SAMPLE_SIZE = 20_000;

/** The speed that fills the colour scale and the speed trace: a high percentile of a sample, so a few tracking spikes do not flatten the rest. */
export function speedTop(speed: Float64Array): number {
  const step = Math.max(1, Math.floor(speed.length / SAMPLE_SIZE));
  const sample: number[] = [];
  for (let i = 0; i < speed.length; i += step) if (Number.isFinite(speed[i])) sample.push(speed[i]);
  sample.sort((a, b) => a - b);
  return (sample.length && sample[Math.floor(SPEED_PERCENTILE * (sample.length - 1))]) || 1;
}
