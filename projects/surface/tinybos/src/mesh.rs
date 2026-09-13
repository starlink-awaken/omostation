//! P2P mesh networking — WireGuard-based LAN self-organization.

use std::collections::HashMap;
use std::time::Instant;

/// Identity of a mesh peer.
#[derive(Debug, Clone)]
pub struct PeerInfo {
    pub node_id: String,
    pub endpoint: String,
    pub public_key: String,
    pub last_seen: Option<Instant>,
    pub is_alive: bool,
}

/// Mesh node registry and routing table.
pub struct MeshTable {
    peers: HashMap<String, PeerInfo>,
    local_id: String,
}

impl MeshTable {
    pub fn new(local_id: impl Into<String>) -> Self {
        Self {
            peers: HashMap::new(),
            local_id: local_id.into(),
        }
    }

    pub fn register(&mut self, peer: PeerInfo) {
        self.peers.insert(peer.node_id.clone(), peer);
    }

    pub fn remove(&mut self, node_id: &str) {
        self.peers.remove(node_id);
    }

    pub fn get_alive(&self) -> Vec<&PeerInfo> {
        self.peers.values().filter(|p| p.is_alive).collect()
    }

    pub fn peer_count(&self) -> usize {
        self.peers.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn register_and_count() {
        let mut table = MeshTable::new("self");
        table.register(PeerInfo {
            node_id: "a".into(),
            endpoint: "10.0.0.1:9100".into(),
            public_key: "key_a".into(),
            last_seen: None,
            is_alive: true,
        });
        assert_eq!(table.peer_count(), 1);
        assert_eq!(table.get_alive().len(), 1);
    }
}
