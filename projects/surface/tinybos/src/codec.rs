//! Wire codec — binary frame encoding/decoding for mesh communication.
//!
//! Frame layout:
//!   magic(4) | version(1) | type(1) | flags(2) | payload_len(4) | digest(4) | payload(var)

use std::fmt;

pub const MAGIC: &[u8; 4] = b"tBOS";
pub const VERSION: u8 = 0x01;
pub const HEADER_SIZE: usize = 16;
pub const MAX_PAYLOAD: usize = 65_536;

#[derive(Debug, Clone, Copy, PartialEq, Eq)]
#[repr(u8)]
pub enum FrameType {
    Ping = 0x01,
    Pong = 0x02,
    Data = 0x10,
    Discovery = 0x20,
    DiscoveryAck = 0x21,
    RouteUpdate = 0x30,
    RoamAnnounce = 0x40,
}

impl fmt::Display for FrameType {
    fn fmt(&self, f: &mut fmt::Formatter<'_>) -> fmt::Result {
        write!(f, "{:?}", self)
    }
}

#[derive(Debug, thiserror::Error)]
pub enum CodecError {
    #[error("payload too large: {0} > {1}")]
    PayloadTooLarge(usize, usize),
    #[error("frame too short: {0} < {1}")]
    FrameTooShort(usize, usize),
    #[error("bad magic: {0:?}")]
    BadMagic([u8; 4]),
    #[error("unsupported version: {0}")]
    UnsupportedVersion(u8),
    #[error("digest mismatch")]
    DigestMismatch,
    #[error("truncated payload: got {0}, expected {1}")]
    Truncated(usize, usize),
}

/// Compute the 4-byte integrity digest (first 4 bytes of SHA-256).
pub fn compute_digest(payload: &[u8]) -> [u8; 4] {
    use sha2::{Digest, Sha256};
    let hash = Sha256::digest(payload);
    let mut digest = [0u8; 4];
    digest.copy_from_slice(&hash[..4]);
    digest
}

/// Encode a frame into wire format.
pub fn encode_frame(frame_type: FrameType, payload: &[u8], flags: u16) -> Result<Vec<u8>, CodecError> {
    if payload.len() > MAX_PAYLOAD {
        return Err(CodecError::PayloadTooLarge(payload.len(), MAX_PAYLOAD));
    }

    let mut frame = Vec::with_capacity(HEADER_SIZE + payload.len());
    frame.extend_from_slice(MAGIC);
    frame.push(VERSION);
    frame.push(frame_type as u8);
    frame.extend_from_slice(&flags.to_be_bytes());
    frame.extend_from_slice(&(payload.len() as u32).to_be_bytes());

    let digest = compute_digest(payload);
    frame.extend_from_slice(&digest);
    frame.extend_from_slice(payload);

    Ok(frame)
}

/// Decode a frame from wire format.
pub fn decode_frame(data: &[u8]) -> Result<(FrameType, u16, &[u8]), CodecError> {
    if data.len() < HEADER_SIZE {
        return Err(CodecError::FrameTooShort(data.len(), HEADER_SIZE));
    }

    let magic = &data[..4];
    if magic != *MAGIC {
        let mut m = [0u8; 4];
        m.copy_from_slice(magic);
        return Err(CodecError::BadMagic(m));
    }

    let version = data[4];
    if version != VERSION {
        return Err(CodecError::UnsupportedVersion(version));
    }

    let frame_type = match data[5] {
        0x01 => FrameType::Ping,
        0x02 => FrameType::Pong,
        0x10 => FrameType::Data,
        0x20 => FrameType::Discovery,
        0x21 => FrameType::DiscoveryAck,
        0x30 => FrameType::RouteUpdate,
        0x40 => FrameType::RoamAnnounce,
        n => return Err(CodecError::UnsupportedVersion(n)),
    };

    let flags = u16::from_be_bytes([data[6], data[7]]);
    let payload_len = u32::from_be_bytes([data[8], data[9], data[10], data[11]]) as usize;

    let digest = &data[12..HEADER_SIZE];
    let payload = &data[HEADER_SIZE..];

    if payload.len() < payload_len {
        return Err(CodecError::Truncated(payload.len(), payload_len));
    }

    let expected = compute_digest(&payload[..payload_len]);
    if digest != expected {
        return Err(CodecError::DigestMismatch);
    }

    Ok((frame_type, flags, &payload[..payload_len]))
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn roundtrip_ping() {
        let frame = encode_frame(FrameType::Ping, &[], 0).unwrap();
        let (ft, flags, payload) = decode_frame(&frame).unwrap();
        assert_eq!(ft, FrameType::Ping);
        assert_eq!(flags, 0);
        assert!(payload.is_empty());
    }

    #[test]
    fn roundtrip_data() {
        let payload = b"hello tinybos";
        let frame = encode_frame(FrameType::Data, payload, 0xBEEF).unwrap();
        let (ft, flags, decoded) = decode_frame(&frame).unwrap();
        assert_eq!(ft, FrameType::Data);
        assert_eq!(flags, 0xBEEF);
        assert_eq!(decoded, payload);
    }

    #[test]
    fn bad_magic() {
        let mut frame = encode_frame(FrameType::Ping, &[], 0).unwrap();
        frame[0] = 0xFF;
        assert!(matches!(decode_frame(&frame), Err(CodecError::BadMagic(_))));
    }

    #[test]
    fn digest_corruption() {
        let mut frame = encode_frame(FrameType::Data, b"test", 0).unwrap();
        frame[HEADER_SIZE] ^= 0xFF;
        assert!(matches!(decode_frame(&frame), Err(CodecError::DigestMismatch)));
    }
}
