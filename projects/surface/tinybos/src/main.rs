//! TinyBOS Edge Daemon — ultra-lightweight physical-world sensing guardian.
//!
//! Binary footprint target: < 10 MB runtime memory.
//! Responsibilities:
//! - Heart-rate variability (HRV) monitoring
//! - Fall detection via accelerometer
//! - Spatial displacement tracking
//! - P2P mesh connectivity over WireGuard
//! - Roaming handoff to backup host on workstation sleep

use std::time::{SystemTime, UNIX_EPOCH};

pub mod codec;
pub mod mesh;
pub mod sensor;

/// Current daemon version.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Milliseconds since Unix epoch.
pub fn now_ms() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64
}

fn main() {
    eprintln!("TinyBOS edge daemon v{}", VERSION);
    eprintln!("TODO: wire up sensor pipeline + mesh + IPC");
}
