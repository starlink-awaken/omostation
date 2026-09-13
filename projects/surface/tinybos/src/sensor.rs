//! Sensor signal types and thresholds.

/// Sensor type codes (must match Python bridge).
pub const SENSOR_HRV: u8 = 0x01;
pub const SENSOR_ACCEL: u8 = 0x02;
pub const SENSOR_GYRO: u8 = 0x03;
pub const SENSOR_BARO: u8 = 0x04;

/// HRV below this RMSSD (ms) is considered critical.
pub const HRV_CRITICAL_LOW: f32 = 20.0;

/// Acceleration magnitude above this (g) indicates possible fall.
pub const FALL_IMPACT_THRESHOLD: f32 = 4.0;

/// Spatial displacement threshold in meters.
pub const DISPLACEMENT_THRESHOLD: f32 = 5.0;

/// A decoded sensor reading.
#[derive(Debug, Clone, PartialEq)]
pub struct SensorReading {
    pub sensor_type: u8,
    pub timestamp_ms: u64,
    pub precision: u16,
    pub values: Vec<f32>,
}

/// Encode a sensor reading into binary frame format.
pub fn encode_sensor_frame(reading: &SensorReading) -> Vec<u8> {
    let mut frame = Vec::new();
    frame.push(reading.sensor_type);
    frame.extend_from_slice(&reading.timestamp_ms.to_le_bytes());
    frame.extend_from_slice(&reading.precision.to_le_bytes());
    frame.push(reading.values.len() as u8);
    for v in &reading.values {
        frame.extend_from_slice(&v.to_le_bytes());
    }
    frame
}

/// Decode a binary sensor frame.
pub fn decode_sensor_frame(data: &[u8]) -> Option<SensorReading> {
    if data.len() < 12 {
        return None;
    }
    let sensor_type = data[0];
    let timestamp_ms = u64::from_le_bytes(data[1..9].try_into().ok()?);
    let precision = u16::from_le_bytes(data[9..11].try_into().ok()?);
    let value_count = data[11] as usize;

    let expected_len = 12 + value_count * 4;
    if data.len() < expected_len {
        return None;
    }

    let mut values = Vec::with_capacity(value_count);
    for i in 0..value_count {
        let offset = 12 + i * 4;
        let v = f32::from_le_bytes(data[offset..offset + 4].try_into().ok()?);
        values.push(v);
    }

    Some(SensorReading {
        sensor_type,
        timestamp_ms,
        precision,
        values,
    })
}

/// Compute the magnitude of a 3-axis acceleration vector.
pub fn accel_magnitude(x: f32, y: f32, z: f32) -> f32 {
    (x * x + y * y + z * z).sqrt()
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn encode_decode_roundtrip() {
        let reading = SensorReading {
            sensor_type: SENSOR_ACCEL,
            timestamp_ms: 1_700_000_000_000,
            precision: 3,
            values: vec![0.1, -0.2, 9.8],
        };
        let encoded = encode_sensor_frame(&reading);
        let decoded = decode_sensor_frame(&encoded).unwrap();
        assert_eq!(decoded.sensor_type, SENSOR_ACCEL);
        assert_eq!(decoded.timestamp_ms, 1_700_000_000_000);
        assert_eq!(decoded.precision, 3);
        assert_eq!(decoded.values, vec![0.1, -0.2, 9.8]);
    }

    #[test]
    fn decode_too_short() {
        assert!(decode_sensor_frame(&[1, 2, 3]).is_none());
    }

    #[test]
    fn accel_magnitude_unit() {
        let mag = accel_magnitude(0.0, 0.0, 1.0);
        assert!((mag - 1.0).abs() < 0.001);
    }

    #[test]
    fn fall_detection() {
        let mag = accel_magnitude(3.0, 3.0, 3.0);
        assert!(mag > FALL_IMPACT_THRESHOLD);
    }
}
