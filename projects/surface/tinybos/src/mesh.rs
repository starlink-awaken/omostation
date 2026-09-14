//! P2P mesh networking — WireGuard-based LAN self-organization.

use std::collections::HashMap;
use std::time::{Duration, Instant};

/// Identity of a mesh peer.
#[derive(Debug, Clone)]
pub struct PeerInfo {
    pub node_id: String,
    pub endpoint: String,
    pub public_key: String,
    pub last_seen: Option<Instant>,
    pub is_alive: bool,
}

impl PeerInfo {
    /// Create a new peer with `last_seen` set to now.
    pub fn new(node_id: impl Into<String>, endpoint: impl Into<String>, public_key: impl Into<String>) -> Self {
        Self {
            node_id: node_id.into(),
            endpoint: endpoint.into(),
            public_key: public_key.into(),
            last_seen: Some(Instant::now()),
            is_alive: true,
        }
    }

    /// Refresh the last-seen timestamp.
    pub fn touch(&mut self) {
        self.last_seen = Some(Instant::now());
        self.is_alive = true;
    }

    /// Check if this peer is stale (not seen within `timeout`).
    pub fn is_stale(&self, timeout: Duration) -> bool {
        match self.last_seen {
            Some(ts) => ts.elapsed() > timeout,
            None => true,
        }
    }
}

/// Default timeout for peer staleness detection.
pub const DEFAULT_PEER_TIMEOUT: Duration = Duration::from_secs(30);

/// Mesh node registry and routing table.
pub struct MeshTable {
    peers: HashMap<String, PeerInfo>,
    local_id: String,
    stale_timeout: Duration,
}

impl MeshTable {
    pub fn new(local_id: impl Into<String>) -> Self {
        Self {
            peers: HashMap::new(),
            local_id: local_id.into(),
            stale_timeout: DEFAULT_PEER_TIMEOUT,
        }
    }

    pub fn with_timeout(local_id: impl Into<String>, timeout: Duration) -> Self {
        Self {
            peers: HashMap::new(),
            local_id: local_id.into(),
            stale_timeout: timeout,
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

    pub fn get(&self, node_id: &str) -> Option<&PeerInfo> {
        self.peers.get(node_id)
    }

    pub fn peer_count(&self) -> usize {
        self.peers.len()
    }

    pub fn local_id(&self) -> &str {
        &self.local_id
    }

    /// Mark a peer as seen (refresh timestamp).
    pub fn touch_peer(&mut self, node_id: &str) -> bool {
        if let Some(peer) = self.peers.get_mut(node_id) {
            peer.touch();
            true
        } else {
            false
        }
    }

    /// Prune stale peers. Returns the number of peers removed.
    pub fn prune_stale(&mut self) -> usize {
        let before = self.peers.len();
        self.peers.retain(|_, peer| {
            if peer.is_stale(self.stale_timeout) {
                peer.is_alive = false;
                false
            } else {
                true
            }
        });
        before - self.peers.len()
    }

    /// Remove only dead (not stale) peers.
    pub fn remove_dead(&mut self) -> usize {
        let before = self.peers.len();
        self.peers.retain(|_, peer| peer.is_alive);
        before - self.peers.len()
    }
}

#[cfg(test)]
mod tests {
    use super::*;

    fn make_peer(id: &str) -> PeerInfo {
        PeerInfo::new(id, "10.0.0.1:9100", "key_x")
    }

    #[test]
    fn register_and_count() {
        let mut table = MeshTable::new("self");
        table.register(make_peer("a"));
        assert_eq!(table.peer_count(), 1);
        assert_eq!(table.get_alive().len(), 1);
    }

    #[test]
    fn get_peer() {
        let mut table = MeshTable::new("self");
        table.register(make_peer("a"));
        assert!(table.get("a").is_some());
        assert!(table.get("b").is_none());
    }

    #[test]
    fn touch_peer() {
        let mut table = MeshTable::new("self");
        table.register(make_peer("a"));
        assert!(table.touch_peer("a"));
        assert!(!table.touch_peer("b"));
    }

    #[test]
    fn remove_peer() {
        let mut table = MeshTable::new("self");
        table.register(make_peer("a"));
        table.remove("a");
        assert_eq!(table.peer_count(), 0);
    }

    #[test]
    fn prune_stale_empty() {
        let mut table = MeshTable::new("self");
        assert_eq!(table.prune_stale(), 0);
    }

    #[test]
    fn peer_is_stale_immediately_if_no_last_seen() {
        let peer = PeerInfo {
            node_id: "x".into(),
            endpoint: "ep".into(),
            public_key: "k".into(),
            last_seen: None,
            is_alive: true,
        };
        assert!(peer.is_stale(Duration::from_secs(1)));
    }

    #[test]
    fn local_id() {
        let table = MeshTable::new("node-1");
        assert_eq!(table.local_id(), "node-1");
    }
}
