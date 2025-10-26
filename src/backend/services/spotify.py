
import os
import time
import math
import pandas as pd
from typing import List, Dict, Any, Optional
from dateutil import tz
import spotipy
from spotipy.oauth2 import SpotifyOAuth

SCOPES = [
    "user-read-email",
    "user-read-private",
    "user-top-read",
    "user-read-recently-played",
    "user-read-playback-state",
    "user-library-read",
    "playlist-read-private",
    "playlist-read-collaborative",
    "user-follow-read",
]

class SpotifyStats:
    def __init__(self,
                 client_id: Optional[str] = None,
                 client_secret: Optional[str] = None,
                 redirect_uri: Optional[str] = None,
                 cache_path: str = ".cache"):
        client_id = client_id or os.getenv("SPOTIFY_CLIENT_ID")
        client_secret = client_secret or os.getenv("SPOTIFY_CLIENT_SECRET")
        redirect_uri = redirect_uri or os.getenv("SPOTIFY_REDIRECT_URI")
        if not all([client_id, client_secret, redirect_uri]):
            raise ValueError("Set SPOTIFY_CLIENT_ID, SPOTIFY_CLIENT_SECRET, SPOTIFY_REDIRECT_URI.")

        auth = SpotifyOAuth(
            client_id=client_id,
            client_secret=client_secret,
            redirect_uri=redirect_uri,
            scope=" ".join(SCOPES),
            cache_path=cache_path,
            show_dialog=False,
            open_browser=True,
        )
        self.sp = spotipy.Spotify(auth_manager=auth)

    # ---------- Basic profile ----------
    def me(self):
        """Your user profile (id, display_name, followers, product, etc.)."""
        return self.sp.me()

    # ---------- Top items ----------
    def top_tracks(self, time_range="medium_term", limit=50, offset=0):
        """
        time_range: 'short_term' ~4 weeks, 'medium_term' ~6 months, 'long_term' several years
        """
        return self.sp.current_user_top_tracks(limit=limit, offset=offset, time_range=time_range)

    def top_artists(self, time_range="medium_term", limit=50, offset=0):
        return self.sp.current_user_top_artists(limit=limit, offset=offset, time_range=time_range)

    # ---------- Recently played (last ~50 plays, usually ~24h window) ----------
    def recently_played(self, limit=50, after_ms: Optional[int] = None, before_ms: Optional[int] = None):
        return self.sp.current_user_recently_played(limit=limit, after=after_ms, before=before_ms)

    # ---------- Playback ----------
    def current_playback(self):
        """Current playback state (device, item, progress_ms, is_playing, shuffle/repeat)."""
        return self.sp.current_playback()

    def devices(self):
        return self.sp.devices()

    # ---------- Library ----------
    def saved_tracks(self, limit=50):
        return self._paged(lambda **kw: self.sp.current_user_saved_tracks(**kw), limit_key="limit", item_key="items", page_limit=limit)

    def saved_albums(self, limit=50):
        return self._paged(lambda **kw: self.sp.current_user_saved_albums(**kw), limit_key="limit", item_key="items", page_limit=limit)

    def saved_shows(self, limit=50):
        return self._paged(lambda **kw: self.sp.current_user_saved_shows(**kw), limit_key="limit", item_key="items", page_limit=limit)

    # ---------- Playlists & follows ----------
    def my_playlists(self, limit=50):
        return self._paged(lambda **kw: self.sp.current_user_playlists(**kw), limit_key="limit", item_key="items", page_limit=limit)

    def playlist_tracks(self, playlist_id: str, limit=100):
        return self._paged(lambda **kw: self.sp.playlist_items(playlist_id, **kw), limit_key="limit", item_key="items", page_limit=limit)

    def followed_artists(self, limit=50):
        items, after = [], None
        while True:
            resp = self.sp.current_user_followed_artists(limit=limit, after=after)
            artists = resp.get("artists", {})
            items.extend(artists.get("items", []))
            after = artists.get("cursors", {}).get("after")
            if not after:
                break
        return items

    # ---------- Audio features / analysis ----------
    def audio_features_for_tracks(self, track_ids: List[str]) -> List[Dict[str, Any]]:
        features = []
        for i in range(0, len(track_ids), 100):
            chunk = track_ids[i:i+100]
            features.extend(self.sp.audio_features(chunk))
        return features

    def audio_analysis(self, track_id: str) -> Dict[str, Any]:
        return self.sp.audio_analysis(track_id)

    # ---------- Convenience: DataFrames + aggregates ----------
    def top_tracks_with_features_df(self, time_range="medium_term", limit=50):
        top = self.top_tracks(time_range=time_range, limit=limit)
        tracks = top.get("items", [])
        ids = [t["id"] for t in tracks if t and t.get("id")]
        feats = self.audio_features_for_tracks(ids)
        df_tracks = pd.json_normalize(tracks)
        df_feats = pd.json_normalize([f for f in feats if f])
        df = df_tracks.merge(df_feats, left_on="id", right_on="id", how="left", suffixes=("", "_feat"))
        return df

    def aggregate_audio_stats(self, features: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Computes averages over common audio features.
        """
        numeric_keys = ["danceability","energy","speechiness","acousticness","instrumentalness",
                        "liveness","valence","tempo","loudness"]
        agg = {}
        valid = [f for f in features if f]
        n = len(valid)
        if n == 0:
            return {k: None for k in numeric_keys} | {"count": 0}
        for k in numeric_keys:
            vals = [f[k] for f in valid if f.get(k) is not None]
            agg[k] = sum(vals)/len(vals) if vals else None
        agg["key_mode_counts"] = self._key_mode_hist(valid)
        agg["count"] = n
        return agg

    # ---------- Helpers ----------
    def _paged(self, func, limit_key="limit", item_key="items", page_limit=50):
        # Generic pager for endpoints that use offset+limit
        out, offset = [], 0
        while True:
            resp = func(offset=offset, **{limit_key: min(page_limit, 50)})
            items = resp.get(item_key, [])
            out.extend(items)
            if len(items) < min(page_limit, 50):
                break
            offset += len(items)
        return out

    @staticmethod
    def _key_mode_hist(features):
        # Returns a simple histogram of musical key & mode across tracks
        # key: 0..11 (C..B), mode: 0 minor, 1 major
        from collections import Counter
        cm = Counter((f.get("key"), f.get("mode")) for f in features if f.get("key") is not None)
        return dict(cm)


# ----------------- Example usage -----------------
if __name__ == "__main__":
    s = SpotifyStats()

    me = s.me()
    print(f"Hello {me.get('display_name')} (id={me.get('id')})")

    # Top tracks & audio features
    df = s.top_tracks_with_features_df(time_range="long_term", limit=50)
    print(df[["name","artists","album.name","tempo","danceability","energy","valence"]].head(10))

    # Aggregate audio stats over your long-term top tracks
    feats = s.audio_features_for_tracks(df["id"].dropna().tolist())
    agg = s.aggregate_audio_stats(feats)
    print("\nAverages over your top tracks (long_term):")
    for k, v in agg.items():
        if k != "key_mode_counts":
            print(f"  {k}: {v}")
    print("Key/Mode histogram:", agg["key_mode_counts"])

    # Recently played (most recent first)
    recent = s.recently_played(limit=50)
    print(f"\nRecently played count: {len(recent.get('items', []))}")

    # Current playback
    play = s.current_playback()
    if play and play.get("item"):
        item = play["item"]
        print(f"\nNow playing: {item.get('name')} — {', '.join(a['name'] for a in item.get('artists', []))}")

    # Library counts
    print(f"\nSaved tracks fetched: {len(s.saved_tracks(limit=50))}")
    print(f"Saved albums fetched: {len(s.saved_albums(limit=50))}")
    print(f"Followed artists fetched: {len(s.followed_artists(limit=50))}")

    # Playlists overview
    playlists = s.my_playlists(limit=50)
    print(f"\nPlaylists: {len(playlists)} (first 5 names): {[p['name'] for p in playlists[:5]]}")

    # Example: fetch full playlist items and their audio features
    if playlists:
        pid = playlists[0]["id"]
        items = s.playlist_tracks(pid)
        track_ids = [it["track"]["id"] for it in items if it.get("track") and it["track"].get("id")]
        feats = s.audio_features_for_tracks(track_ids)
        agg_pl = s.aggregate_audio_stats(feats)
        print(f"\nPlaylist '{playlists[0]['name']}' — tracks: {len(track_ids)} — avg tempo: {agg_pl.get('tempo')}")
