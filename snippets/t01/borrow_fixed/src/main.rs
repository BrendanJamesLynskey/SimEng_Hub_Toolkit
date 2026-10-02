// The fix used throughout the engine: pass an index, not a reference.
// Each borrow of `self.requests[rid]` ends before the next statement.
struct Request { finish: Option<f64> }

struct Sim { now: f64, requests: Vec<Request>, done: usize }

impl Sim {
    fn finish(&mut self, rid: usize) {
        self.requests[rid].finish = Some(self.now);
        self.done += 1;
    }

    fn step(&mut self) {
        let rid = 0;          // events and queues carry indices into an arena
        self.finish(rid);
    }
}

fn main() {
    let mut s = Sim { now: 1.0, requests: vec![Request { finish: None }], done: 0 };
    s.step();
    println!("{:?} {}", s.requests[0].finish, s.done);
}
