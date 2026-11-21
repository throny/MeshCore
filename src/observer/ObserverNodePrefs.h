#pragma once

#include <helpers/CommonCLI.h>
#include "ObserverPolicy.h"

namespace observer {

// ConfigSerializer keeps at most CONFIG_MAX_KEYLEN-1 characters of a key and a longer key
// in prefs.json aborts the whole load, so every key below must stay within that limit.
namespace prefs_key {
constexpr size_t len(const char* s) { return *s ? 1 + len(s + 1) : 0; }
constexpr const char* kVersion = "observer_v";
constexpr const char* kEnabled = "observer_en";
constexpr const char* kPeerPresent = "observer_p_on";
constexpr const char* kPeerType = "observer_p_type";
constexpr const char* kPeerAddress = "observer_p_addr";
static_assert(len(kVersion) < CONFIG_MAX_KEYLEN, "prefs key too long");
static_assert(len(kEnabled) < CONFIG_MAX_KEYLEN, "prefs key too long");
static_assert(len(kPeerPresent) < CONFIG_MAX_KEYLEN, "prefs key too long");
static_assert(len(kPeerType) < CONFIG_MAX_KEYLEN, "prefs key too long");
static_assert(len(kPeerAddress) < CONFIG_MAX_KEYLEN, "prefs key too long");
}  // namespace prefs_key

class ObserverNodePrefs : public NodePrefs {
 public:
  static constexpr uint8_t kObserverVersion = 1;
  uint8_t observer_enabled = 0;
  uint8_t observer_peer_present = 0;
  uint8_t observer_peer_type = 0;
  uint8_t observer_peer_address[6]{};
  uint8_t observer_version_ = 0;

 protected:
  void structure() override {
    NodePrefs::structure();
    def(prefs_key::kVersion, observer_version_);
    def(prefs_key::kEnabled, observer_enabled);
    def(prefs_key::kPeerPresent, observer_peer_present);
    def(prefs_key::kPeerType, observer_peer_type);
    def(prefs_key::kPeerAddress, observer_peer_address, sizeof(observer_peer_address));
  }

 public:
  template <typename Save>
  bool persistEnabled(bool enabled, Save save) {
    const uint8_t previous_enabled = observer_enabled;
    const uint8_t previous_version = observer_version_;
    const uint8_t previous_peer_present = observer_peer_present;
    const uint8_t previous_peer_type = observer_peer_type;
    uint8_t previous_peer_address[sizeof(observer_peer_address)];
    memcpy(previous_peer_address, observer_peer_address, sizeof(previous_peer_address));

    observer_version_ = kObserverVersion;
    observer_enabled = enabled ? 1 : 0;
    if (previous_version != kObserverVersion) {
      observer_peer_present = 0;
      observer_peer_type = 0;
      memset(observer_peer_address, 0, sizeof(observer_peer_address));
    }
    if (save()) return true;
    observer_enabled = previous_enabled;
    observer_version_ = previous_version;
    observer_peer_present = previous_peer_present;
    observer_peer_type = previous_peer_type;
    memcpy(observer_peer_address, previous_peer_address, sizeof(previous_peer_address));
    return false;
  }

  template <typename Save>
  bool persistPeer(bool has_peer, const PeerIdentity& peer, Save save) {
    const uint8_t previous_present = observer_peer_present;
    const uint8_t previous_version = observer_version_;
    const uint8_t previous_enabled = observer_enabled;
    const uint8_t previous_type = observer_peer_type;
    uint8_t previous_address[sizeof(observer_peer_address)];
    memcpy(previous_address, observer_peer_address, sizeof(previous_address));

    observer_version_ = kObserverVersion;
    observer_peer_present = has_peer ? 1 : 0;
    observer_peer_type = peer.type;
    memcpy(observer_peer_address, peer.address, sizeof(peer.address));
    if (save()) return true;
    observer_peer_present = previous_present;
    observer_version_ = previous_version;
    observer_enabled = previous_enabled;
    observer_peer_type = previous_type;
    memcpy(observer_peer_address, previous_address, sizeof(previous_address));
    return false;
  }
};

}  // namespace observer
