# Flick Range

A browser aim trainer with four drills: Gridshot, Spidershot, Microshot and Strafe Track.

Open `index.html` in a desktop browser and click a drill. The game locks your mouse; press Esc to pause.

Sensitivity uses Valorant's scale (0.07° per mouse count at sens 1). Set it with the slider on the menu or pause screen, or press [ and ] while playing. Settings also use Valorant's horizontal FOV and show your eDPI and cm per 360°.

## More games

Each game is a single page with no build step. Open its `index.html` in a desktop browser.

### Neon Drift (`neon-drift/`)

3D racing on five tracks: four neon city circuits at night, plus **Spa**, a daytime forest track based on the real Spa-Francorchamps layout. It has La Source, the Eau Rouge/Raidillon climb, the Kemmel straight, Pouhon, Blanchimont and the Bus Stop chicane, and its hills slow you uphill and speed you up downhill.

- **Race** against 0–5 AI drivers on Easy, Normal or Hard.
- **Time Trial** races your fastest lap, shown as a ghost car.
- **Split Screen** for two players on one keyboard (WASD and arrow keys), or with two gamepads.
- **Online** races with up to 6 cars. Bots can fill the empty spots.

Drift with Space to fill your boost meter, then press Shift to boost. The yellow arrows on the track give a free boost. Press C to switch between the chase, far and hood cameras (player 2 uses the `.` key).

The 3D graphics use [three.js](https://threejs.org) (MIT, included in `shared/three.min.js`). They need a browser with WebGL, which almost every modern browser has.

### Bastion (`bastion/`)

Grid tower defense: hold off 30 waves, then keep going in endless mode.

- 13 towers, each with 4 levels: Bolt, Cannon, Frost, Tesla, Beam, Mortar, Sniper, Flamer (sets enemies on fire), Poison (toxic clouds), Rocket (3× vs flyers), Railgun (hits everything in a line), Banner (boosts nearby towers) and Gold Mine (earns gold every wave).
- 9 enemy types, including armored Brutes, Healers, Splitters, flying Wisps that take a straight route, and a Warlord boss every 10 waves.
- 3 maps and 3 difficulties: Easy, Medium and Hard.
- **Online co-op** for up to 4 players. Everyone earns gold from every kill and builds their own towers. You can give gold to teammates and ping the map with F. Enemies get tougher as more players join.

### Online play

Online modes use room codes. One player hosts and gets a 5-letter code, and friends join with it (or with the invite link). Players connect directly through WebRTC using [PeerJS](https://peerjs.com) (MIT, included in `shared/peerjs.min.js`). The free PeerJS server only introduces players to each other, so there is nothing to set up or host.

- Friends need to load the games from a web address, for example GitHub Pages or `python3 -m http.server`.
- The host's game runs the race or the waves, so the host should keep their tab open and visible.
- Some strict school or office networks block direct connections. If joining fails, try another network.
