//! Python writes a cube root as `abs(x) ** (1 / 3)`; Rust offers `f64::cbrt`.
//! They are different functions, so a port must copy the expression, not the intent.

fn main() {
    let (mut differ, mut total) = (0u32, 0u32);
    let mut x = 1e-3_f64;
    while x < 1e6 {
        total += 1;
        if x.cbrt() != x.powf(1.0 / 3.0) {
            differ += 1;
        }
        x *= 1.000123; // a geometric sweep over nine decades
    }
    println!("{differ} of {total} values differ");
    println!(
        "0.001: cbrt {:?}, powf(1/3) {:?}",
        0.001f64.cbrt(),
        0.001f64.powf(1.0 / 3.0)
    );
}
