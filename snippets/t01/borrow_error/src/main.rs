// The tempting design, which the borrow checker rejects: hold a reference to a
// request while the simulation that owns it is mutated.
struct Request { finish: Option<f64> }

struct Sim { now: f64, requests: Vec<Request>, done: usize }

impl Sim {
    fn finish(&mut self, r: &mut Request) {
        r.finish = Some(self.now);
        self.done += 1;
    }

    fn step(&mut self) {
        let r = &mut self.requests[0];   // a mutable borrow of part of self ...
        self.finish(r);                  // ... while self is borrowed mutably again
    }
}

fn main() {
    let mut s = Sim { now: 1.0, requests: vec![Request { finish: None }], done: 0 };
    s.step();
    println!("{:?} {}", s.requests[0].finish, s.done);
}
