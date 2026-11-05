/*
 * Room-code multiplayer on top of PeerJS (WebRTC data channels).
 *
 * One player hosts and gets a 5-letter code. Everyone else joins with that code.
 * All traffic goes through the host (star layout), so the host's game is the
 * source of truth.
 *
 * For testing against a local PeerJS server, add ?peerhost=localhost&peerport=9000
 * to the page URL.
 */
(function () {
  'use strict';

  const LETTERS = 'ABCDEFGHJKLMNPQRSTUVWXYZ'; // no I or O, they look like 1 and 0
  const NAMESPACE = 'flickrange-arcade-';

  function peerOptions() {
    const q = new URLSearchParams(location.search);
    const opts = { debug: 0 };
    if (q.get('peerhost')) {
      opts.host = q.get('peerhost');
      opts.port = Number(q.get('peerport')) || 9000;
      opts.path = q.get('peerpath') || '/';
      opts.secure = q.get('peersecure') === '1';
    }
    return opts;
  }

  function randomCode() {
    let c = '';
    for (let i = 0; i < 5; i++) c += LETTERS[Math.floor(Math.random() * LETTERS.length)];
    return c;
  }

  function cleanCode(code) {
    return String(code || '').toUpperCase().replace(/[^A-Z]/g, '').slice(0, 5);
  }

  class Room {
    constructor(game) {
      this.game = game;
      this.peer = null;
      this.isHost = false;
      this.code = null;
      this.conns = new Map(); // host: peerId -> connection
      this.hostConn = null; // client: connection to host
      this.handlers = {};
      this.maxPlayers = 4;
      this.closed = false;
      this.locked = false; // host: refuse new players (game in progress)
    }

    on(ev, fn) {
      (this.handlers[ev] || (this.handlers[ev] = [])).push(fn);
      return this;
    }

    emit(ev, ...args) {
      (this.handlers[ev] || []).forEach((fn) => {
        try { fn(...args); } catch (e) { console.error(e); }
      });
    }

    get myId() {
      return this.isHost ? 'host' : this.peer && this.peer.id;
    }

    /** Create a room. Resolves with the room code. */
    host(maxPlayers) {
      this.isHost = true;
      this.maxPlayers = maxPlayers || 4;
      return new Promise((resolve, reject) => {
        let tries = 0;
        const attempt = () => {
          const code = randomCode();
          const peer = new Peer(NAMESPACE + this.game + '-' + code, peerOptions());
          let opened = false;
          peer.on('open', () => {
            opened = true;
            this.peer = peer;
            this.code = code;
            resolve(code);
          });
          peer.on('connection', (conn) => this._accept(conn));
          peer.on('disconnected', () => {
            // Lost the signalling server. Existing players stay connected; try to come back.
            if (!this.closed) setTimeout(() => !this.closed && peer.reconnect(), 1000);
          });
          peer.on('error', (err) => {
            if (!opened && err.type === 'unavailable-id' && tries++ < 5) {
              peer.destroy();
              attempt();
            } else if (!opened) {
              reject(friendlyError(err));
            } else {
              console.warn('peer error', err);
            }
          });
        };
        attempt();
      });
    }

    _accept(conn) {
      conn.on('open', () => {
        if (this.locked) {
          conn.send({ t: 'refused', reason: 'That game has already started.' });
          setTimeout(() => conn.close(), 300);
          return;
        }
        if (this.conns.size + 1 >= this.maxPlayers) {
          conn.send({ t: 'refused', reason: 'That room is full.' });
          setTimeout(() => conn.close(), 300);
          return;
        }
        this.conns.set(conn.peer, conn);
        this.emit('join', conn.peer);
      });
      conn.on('data', (msg) => {
        if (this.conns.has(conn.peer)) this.emit('message', msg, conn.peer);
      });
      const gone = () => {
        if (this.conns.delete(conn.peer)) this.emit('leave', conn.peer);
      };
      conn.on('close', gone);
      conn.on('error', gone);
    }

    /** Join a room by code. Resolves once connected to the host. */
    join(code) {
      this.isHost = false;
      code = cleanCode(code);
      return new Promise((resolve, reject) => {
        if (code.length !== 5) return reject(new Error('Room codes are 5 letters.'));
        const peer = new Peer(peerOptions());
        this.peer = peer;
        let done = false;
        const fail = (msg) => {
          if (done) return;
          done = true;
          peer.destroy();
          reject(new Error(msg));
        };
        const timer = setTimeout(() => fail('Could not reach that room. Check the code and try again.'), 12000);
        peer.on('open', () => {
          const conn = peer.connect(NAMESPACE + this.game + '-' + code, { reliable: true, serialization: 'json' });
          conn.on('open', () => {
            this.hostConn = conn;
            this.code = code;
            done = true;
            clearTimeout(timer);
            resolve(code);
          });
          conn.on('data', (msg) => {
            if (msg && msg.t === 'refused') {
              this.emit('refused', msg.reason);
              return;
            }
            this.emit('message', msg, 'host');
          });
          conn.on('close', () => {
            if (!this.closed) this.emit('disconnect');
          });
        });
        peer.on('error', (err) => {
          if (!done) {
            clearTimeout(timer);
            fail(err.type === 'peer-unavailable' ? 'No room with that code.' : friendlyError(err).message);
          } else {
            console.warn('peer error', err);
          }
        });
      });
    }

    /** Client: send to host. Host: send to one player (to = peerId). */
    send(msg, to) {
      if (this.isHost) {
        const c = this.conns.get(to);
        if (c && c.open) c.send(msg);
      } else if (this.hostConn && this.hostConn.open) {
        this.hostConn.send(msg);
      }
    }

    /** Host only: send to every player, optionally skipping one. */
    broadcast(msg, except) {
      if (!this.isHost) return;
      for (const [id, c] of this.conns) if (id !== except && c.open) c.send(msg);
    }

    kick(id) {
      const c = this.conns.get(id);
      if (c) c.close();
    }

    close() {
      this.closed = true;
      if (this.peer) this.peer.destroy();
      this.conns.clear();
      this.hostConn = null;
    }
  }

  function friendlyError(err) {
    const map = {
      'browser-incompatible': 'This browser does not support online play.',
      network: 'Could not reach the matchmaking server. Check your internet connection.',
      'server-error': 'The matchmaking server had a problem. Try again in a moment.',
      'socket-error': 'Could not reach the matchmaking server. Check your internet connection.',
      'socket-closed': 'Lost connection to the matchmaking server.',
      'ssl-unavailable': 'Online play needs a secure connection.',
      webrtc: 'Could not connect to the other player (network blocked).',
    };
    return new Error(map[err && err.type] || (err && err.message) || 'Connection failed.');
  }

  window.ArcadeNet = { Room, cleanCode };
})();
