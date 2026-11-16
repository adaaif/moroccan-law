/** lean-qr's nano build (qr.js): `generate(text, options)` gives the code's modules; `get(x, y)` is a dark one. */
export declare const correction: { readonly L: 0; readonly M: 1; readonly Q: 2; readonly H: 3 };
export type Bitmap = { readonly size: number; get(x: number, y: number): boolean };
export declare function generate(data: string, options?: { minCorrectionLevel?: number; minVersion?: number }): Bitmap;
