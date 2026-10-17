const PERCENT = 100;
const DEGREES_PER_RADIAN = 180 / Math.PI;

/** A share as a percent rounded to the decimals given, 0.9 as "90%" and 0.6364 as "63.6%" at one. */
export const percent = (share: number, decimals = 0): string => `${+(PERCENT * share).toFixed(decimals)}%`;

/** An angle in radians as degrees rounded to the decimals given. A hair under zero is written 0, not -0. */
export const degrees = (radians: number, decimals = 0): string => `${+(radians * DEGREES_PER_RADIAN).toFixed(decimals)} deg`;
