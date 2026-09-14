//! TinyBOS Edge Daemon — ultra-lightweight physical-world sensing guardian.
//!
//! Binary footprint target: < 10 MB runtime memory.
//! Responsibilities:
//! - Heart-rate variability (HRV) monitoring
//! - Fall detection via accelerometer
//! - Spatial displacement tracking
//! - P2P mesh connectivity over WireGuard
//! - Roaming handoff to backup host on workstation sleep

use std::io::Write;
use std::os::unix::net::{UnixListener, UnixStream};
use std::sync::atomic::{AtomicBool, Ordering};
use std::sync::Arc;
use std::time::Duration;

pub mod codec;
pub mod mesh;
pub mod sensor;

use codec::{encode_frame, FrameType};
use mesh::{PeerInfo, MeshTable};
use sensor::{
    accel_magnitude, decode_sensor_frame, encode_sensor_frame, SensorReading, DISPLACEMENT_THRESHOLD,
    FALL_IMPACT_THRESHOLD, HRV_CRITICAL_LOW, SENSOR_ACCEL, SENSOR_HRV,
};

/// Current daemon version.
pub const VERSION: &str = env!("CARGO_PKG_VERSION");

/// Default Unix socket path for IPC.
pub const DEFAULT_SOCKET_PATH: &str = "/tmp/tinybos.sock";

/// Milliseconds since Unix epoch.
pub fn now_ms() -> u64 {
    std::time::SystemTime::now()
        .duration_since(std::time::UNIX_EPOCH)
        .unwrap()
        .as_millis() as u64
}

/// Sensor sampling interval (milliseconds).
const SAMPLE_INTERVAL_MS: u64 = 1000;

/// Maximum number of samples in test-pipeline mode.
const TEST_PIPELINE_SAMPLES: usize = 10;

/// Global shutdown flag (signal-safe).
static SHUTDOWN_FLAG: AtomicBool = AtomicBool::new(false);

/// Install signal handlers: set global flag on SIGTERM/SIGINT.
fn install_signal_handler() {
    extern "C" fn handle_signal(_sig: i32) {
        SHUTDOWN_FLAG.store(true, Ordering::SeqCst);
    }
    unsafe {
        libc::signal(libc::SIGTERM, handle_signal as *const () as usize);
        libc::signal(libc::SIGINT, handle_signal as *const () as usize);
    }
}

/// Simulate a sensor reading for a given cycle index.
/// Cycles through HRV, accelerometer, and displacement patterns.
fn simulate_reading(cycle: usize) -> SensorReading {
    let ts = now_ms();
    match cycle % 3 {
        0 => SensorReading {
            sensor_type: SENSOR_HRV,
            timestamp_ms: ts,
            precision: 2,
            values: vec![65.0 + (cycle as f32 * 2.5).sin() * 10.0],
        },
        1 => SensorReading {
            sensor_type: SENSOR_ACCEL,
            timestamp_ms: ts,
            precision: 2,
            values: vec![0.05, -0.03, 1.0 + (cycle as f32 * 0.1).sin() * 0.05],
        },
        _ => SensorReading {
            sensor_type: SENSOR_ACCEL,
            timestamp_ms: ts,
            precision: 2,
            values: vec![1.0, 2.0, 5.5], // displacement pattern
        },
    }
}

/// Detect if a reading exceeds critical thresholds.
fn detect_alerts(reading: &SensorReading) -> Vec<String> {
    let mut alerts = Vec::new();
    match reading.sensor_type {
        SENSOR_HRV => {
            if let Some(&hrv) = reading.values.first() {
                if hrv < HRV_CRITICAL_LOW {
                    alerts.push(format!("HRV critical low: {hrv:.1} ms"));
                }
            }
        }
        SENSOR_ACCEL => {
            if reading.values.len() >= 3 {
                let mag = accel_magnitude(reading.values[0], reading.values[1], reading.values[2]);
                if mag > FALL_IMPACT_THRESHOLD {
                    alerts.push(format!("Fall detected: {mag:.2}g"));
                }
                // Check displacement
                let disp = (reading.values[0].abs() + reading.values[1].abs() + reading.values[2].abs()) / 3.0;
                if disp > DISPLACEMENT_THRESHOLD {
                    alerts.push(format!("Large displacement: {disp:.1}m"));
                }
            }
        }
        _ => {}
    }
    alerts
}

/// Send a sensor frame over a Unix socket with 4-byte length prefix.
fn send_frame(socket: &mut UnixStream, payload: &[u8]) -> std::io::Result<()> {
    let len = payload.len() as u32;
    socket.write_all(&len.to_le_bytes())?;
    socket.write_all(payload)?;
    Ok(())
}

/// Run the sensor pipeline: sample → encode → send over Unix socket.
fn run_pipeline(socket_path: &str) -> std::io::Result<()> {
    // Clean up stale socket
    let _ = std::fs::remove_file(socket_path);

    let listener = UnixListener::bind(socket_path)?;
    eprintln!("[tinybos] Listening on {socket_path}");

    // Accept connections in a thread
    let accept_stop = Arc::new(AtomicBool::new(false));
    let conns = Arc::new(std::sync::Mutex::new(Vec::<UnixStream>::new()));
    let conns_clone = Arc::clone(&conns);
    let accept_stop_clone = Arc::clone(&accept_stop);

    let _accept_thread = std::thread::spawn(move || -> std::io::Result<()> {
        loop {
            if accept_stop_clone.load(Ordering::SeqCst) || SHUTDOWN_FLAG.load(Ordering::SeqCst) {
                break;
            }
            match listener.accept() {
                Ok((stream, _)) => {
                    eprintln!("[tinybos] Client connected");
                    conns_clone.lock().unwrap().push(stream);
                }
                Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                    std::thread::sleep(Duration::from_millis(100));
                }
                Err(e) => return Err(e),
            }
        }
        Ok(())
    });

    // Sensor sampling loop
    let mut cycle = 0usize;
    loop {
        if SHUTDOWN_FLAG.load(Ordering::SeqCst) {
            break;
        }

        let reading = simulate_reading(cycle);
        let alerts = detect_alerts(&reading);
        if !alerts.is_empty() {
            for alert in &alerts {
                eprintln!("[tinybos][ALERT] {alert}");
            }
        }

        let sensor_payload = encode_sensor_frame(&reading);
        let frame = encode_frame(FrameType::Data, &sensor_payload, 0).unwrap();

        // Send to all connected clients
        {
            let conns_to_send = conns.lock().unwrap();
            for stream in conns_to_send.iter() {
                if let Ok(mut cloned) = stream.try_clone() {
                    if send_frame(&mut cloned, &frame).is_err() {
                        // Client disconnected, skip
                    }
                }
            }
        }

        cycle += 1;
        std::thread::sleep(Duration::from_millis(SAMPLE_INTERVAL_MS));
    }

    accept_stop.store(true, Ordering::SeqCst);
    Ok(())
}

/// Run in test-pipeline mode: send fixed frames over Unix socket, then exit.
/// Used by CI and integration tests.
fn run_test_pipeline(socket_path: &str) -> std::io::Result<()> {
    let _ = std::fs::remove_file(socket_path);

    // Create socket and wait for a connection (like a server)
    let listener = UnixListener::bind(socket_path)?;
    eprintln!("[tinybos:test] Listening on {socket_path}");

    // Wait for connection with timeout
    let _ = listener.set_nonblocking(true);
    let mut connected = None;
    for _ in 0..100 {
        match listener.accept() {
            Ok((stream, _)) => {
                connected = Some(stream);
                break;
            }
            Err(ref e) if e.kind() == std::io::ErrorKind::WouldBlock => {
                std::thread::sleep(Duration::from_millis(50));
            }
            Err(e) => return Err(e),
        }
    }

    let mut stream = match connected {
        Some(s) => s,
        None => {
            eprintln!("[tinybos:test] No client connected, sending to stdout instead");
            return run_test_pipeline_stdout();
        }
    };

    // Send fixed sensor frames
    for i in 0..TEST_PIPELINE_SAMPLES {
        let reading = simulate_reading(i);
        let sensor_payload = encode_sensor_frame(&reading);
        let frame = encode_frame(FrameType::Data, &sensor_payload, 0).unwrap();
        send_frame(&mut stream, &frame)?;
    }

    // Send a Ping frame
    let ping = encode_frame(FrameType::Ping, &[], 0).unwrap();
    send_frame(&mut stream, &ping)?;

    // Send RoamAnnounce
    let roam = encode_frame(FrameType::RoamAnnounce, b"tinybos-roam-v1", 0).unwrap();
    send_frame(&mut stream, &roam)?;

    eprintln!("[tinybos:test] Sent {TEST_PIPELINE_SAMPLES} sensor frames + ping + roam");
    Ok(())
}

/// Fallback: print frames to stdout as hex (for CI without a listener).
fn run_test_pipeline_stdout() -> std::io::Result<()> {
    for i in 0..TEST_PIPELINE_SAMPLES {
        let reading = simulate_reading(i);
        let sensor_payload = encode_sensor_frame(&reading);
        let frame = encode_frame(FrameType::Data, &sensor_payload, 0).unwrap();
        let hex: String = frame.iter().map(|b| format!("{b:02x}")).collect();
        println!("FRAME {i}: {hex}");

        // Verify roundtrip
        let (ft, _flags, payload) = codec::decode_frame(&frame).unwrap();
        assert_eq!(ft, FrameType::Data);
        let decoded = decode_sensor_frame(payload).unwrap();
        assert_eq!(decoded.sensor_type, reading.sensor_type);
    }
    println!("OK: {TEST_PIPELINE_SAMPLES} frames encoded and decoded successfully");
    Ok(())
}

fn main() {
    let args: Vec<String> = std::env::args().collect();
    let socket_path = args
        .iter()
        .find(|a| a.starts_with("--socket="))
        .map(|a| a["--socket=".len()..].to_string())
        .unwrap_or_else(|| DEFAULT_SOCKET_PATH.to_string());

    eprintln!("TinyBOS edge daemon v{VERSION}");
    eprintln!("Socket: {socket_path}");

    // Initialize mesh table with local identity
    let hostname = std::env::var("HOSTNAME").unwrap_or_else(|_| "tinybos-1".to_string());
    let mut mesh_table = MeshTable::new(&hostname);
    mesh_table.register(PeerInfo::new("backup-1", "192.168.1.100:9100", "backup_key"));
    eprintln!("[tinybos] Mesh: {} peers registered", mesh_table.peer_count());

    if args.iter().any(|a| a == "--test-pipeline") {
        if let Err(e) = run_test_pipeline(&socket_path) {
            eprintln!("[tinybos:test] error: {e}");
            std::process::exit(1);
        }
    } else {
        install_signal_handler();

        if let Err(e) = run_pipeline(&socket_path) {
            eprintln!("[tinybos] fatal: {e}");
            std::process::exit(1);
        }
    }

    eprintln!("[tinybos] Shutdown complete");
}
