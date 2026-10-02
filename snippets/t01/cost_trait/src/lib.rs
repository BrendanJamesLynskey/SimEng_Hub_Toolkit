//! A pluggable cost model: the engine asks "how long?", the trait answers.

/// What every cost model must answer. The engine knows nothing else about time.
pub trait CostModel {
    fn prefill(&self, tokens: u64) -> f64;
    fn decode(&self, batch: u64, context: u64) -> f64;
}

/// A ten-line roofline.
pub struct Roofline {
    pub flops: f64, // achievable FLOP/s
    pub bytes: f64, // achievable bytes/s
    pub weight_bytes: f64,
    pub flops_per_token: f64, // 2 x parameters
    pub kv_per_token: f64,
}

impl CostModel for Roofline {
    fn prefill(&self, tokens: u64) -> f64 {
        (self.flops_per_token * tokens as f64 / self.flops).max(self.weight_bytes / self.bytes)
    }
    fn decode(&self, batch: u64, context: u64) -> f64 {
        let compute = self.flops_per_token * batch as f64 / self.flops;
        let memory = (self.weight_bytes + context as f64 * self.kv_per_token) / self.bytes;
        compute.max(memory)
    }
}

/// A measured table, for when a roofline is not good enough.
pub struct Measured {
    pub decode_by_batch: Vec<f64>, // seconds per step, indexed by batch size
}

impl CostModel for Measured {
    fn prefill(&self, tokens: u64) -> f64 {
        1e-4 * tokens as f64
    }
    fn decode(&self, batch: u64, _context: u64) -> f64 {
        let i = (batch as usize).min(self.decode_by_batch.len() - 1);
        self.decode_by_batch[i]
    }
}

/// Static dispatch: one copy of the engine per cost model, every call inlinable.
pub fn total_decode_time<C: CostModel>(cost: &C, steps: u64) -> f64 {
    (0..steps).map(|k| cost.decode(8, 4096 + 8 * k)).sum()
}

/// Dynamic dispatch: one engine, the model chosen at run time (from a config file, say).
pub fn pick(name: &str) -> Box<dyn CostModel> {
    match name {
        "measured" => Box::new(Measured {
            decode_by_batch: vec![0.010, 0.011, 0.012, 0.013],
        }),
        _ => Box::new(Roofline {
            flops: 1e15,
            bytes: 2.7e12,
            weight_bytes: 1.4e11,
            flops_per_token: 1.4e11,
            kv_per_token: 3.3e5,
        }),
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn both_dispatch_styles_give_the_same_answer() {
        let r = Roofline {
            flops: 1e15,
            bytes: 2.7e12,
            weight_bytes: 1.4e11,
            flops_per_token: 1.4e11,
            kv_per_token: 3.3e5,
        };
        let boxed = pick("roofline");
        assert_eq!(r.decode(8, 4096), boxed.decode(8, 4096));
        assert!(total_decode_time(&r, 10) > 10.0 * r.decode(8, 4096));
    }

    #[test]
    fn decode_is_memory_bound_at_small_batch() {
        let r = Roofline {
            flops: 1e15,
            bytes: 2.7e12,
            weight_bytes: 1.4e11,
            flops_per_token: 1.4e11,
            kv_per_token: 3.3e5,
        };
        assert_eq!(r.decode(1, 0), 1.4e11 / 2.7e12);
        assert_eq!(pick("measured").decode(99, 0), 0.013);
    }
}
