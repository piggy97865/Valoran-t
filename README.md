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

Drifting is the heart of the game. Hold Space and steer into a corner to slide sideways while keeping your speed; steer into the drift to tighten it or away to widen it. The longer you hold a drift, the bigger the speed boost when you let go (the sparks turn blue, then orange, then purple). Drifts score points, chaining them builds a combo multiplier, and hitting a wall mid-drift loses that drift's points.

- **Drift Challenge**: score as many drift points as you can in 90 seconds. Your best score is saved for each track.

Drifting also fills your boost meter; press Shift to use it. The yellow arrows on the track give a free boost. Press C to switch between the chase, far and hood cameras (player 2 uses the `.` key).

The 3D graphics use [three.js](https://threejs.org) (MIT, included in `shared/three.min.js`). They need a browser with WebGL, which almost every modern browser has.

### Bastion (`bastion/`)

Grid tower defense: hold off 30 waves, then keep going in endless mode.

- 13 towers, each with 4 levels: Bolt, Cannon, Frost, Tesla, Beam, Mortar, Sniper, Flamer (sets enemies on fire), Poison (toxic clouds), Rocket (3× vs flyers), Railgun (hits everything in a line), Banner (boosts nearby towers) and Gold Mine (earns gold every wave).
- 9 enemy types, including armored Brutes, Healers, Splitters, flying Wisps that take a straight route, and a Warlord boss every 10 waves.
- 3 maps and 3 difficulties: Easy, Medium and Hard.
- Each difficulty has its own special boss at wave 30, which returns stronger every 10 waves in endless mode: the **Jelly King** (Easy) splits into jellies as it takes damage, the **Shield Lord** (Medium) has a shield that recharges if you stop hitting it, and the **Shadow Dragon** (Hard) flies and roars to freeze nearby towers, getting faster when badly hurt.
- **Hardcore** (a 4th difficulty, 15 lives) uses normal enemy health but adds 6 unique enemies with tricks: Blinkers teleport forward, Shellbacks shrug off explosions/fire/poison, Bombers freeze nearby towers when they die, Stormwings are fast flyers that can't be slowed, Broodmothers spawn swarms and Ragers speed up when hurt. Its bosses are the Necromancer (raises fallen enemies as skeletons), the Phantom (turns invisible and teleports) and the Colossus (three layers of armor that crack off, stomps to freeze towers and calls Brutes), who arrives at wave 30 together with the Shield Lord and Shadow Dragon.
- Co-op is harder than solo: enemies get more health and there are more of them for each extra player, and everyone starts with a bit less gold.
- Easy and Medium last 30 waves. Hard and Hardcore last **40 waves** and end with **The Void Emperor**: three orbiting Void Crystals make him immune until you break them, then he opens portals and casts eclipses that freeze towers, and at low health he summons the crystals again and enrages. When he falls he rises again at the start of the path as **The Ascended Emperor**, a winged god of light with golden eye lasers, judgment pillars, light orbs and **Heavenly Descent** (he flies up out of reach, slams down further along the road and rains beams of light on towers), all of which stun towers. The wave 30 bosses on Hard and Hardcore also fight back: the Colossus fires shoulder missiles and the Shadow Dragon spits fireballs that stun towers.
- **Test mode**: open the page with `?test` at the end of the address (or use the "Bastion TEST MODE" download) for infinite lives and gold, a wave picker, and buttons to spawn any enemy or clear the board.
- Endless mode (after the final wave) gets much harder every wave: more and faster enemies with more health, only 10 seconds between waves, and extra Shadow Dragons from wave 40.
- **Online co-op** for up to 4 players. Everyone earns gold from every kill and builds their own towers. You can give gold to teammates and ping the map with F. Enemies get tougher as more players join.

### Online play

Online modes use room codes. One player hosts and gets a 5-letter code, and friends join with it (or with the invite link). Players connect directly through WebRTC using [PeerJS](https://peerjs.com) (MIT, included in `shared/peerjs.min.js`). The free PeerJS server only introduces players to each other, so there is nothing to set up or host.

- Friends need to load the games from a web address, for example GitHub Pages or `python3 -m http.server`.
- The host's game runs the race or the waves, so the host should keep their tab open and visible.
- Some strict school or office networks block direct connections. If joining fails, try another network.
