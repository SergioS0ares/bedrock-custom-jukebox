
import { world, system } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";

const RAW_PLAYLIST = [
    {
        "id": "custom.jukebox.musica_2",
        "name": "Musica 2",
        "duration": 191.57625,
        "icon": null,
        "playlist": "Geral"
    },
    {
        "id": "custom.jukebox.sabo_musica_1",
        "name": "Musica 1",
        "duration": 157.268771,
        "icon": null,
        "playlist": "sab\u00e3o"
    },
    {
        "id": "custom.jukebox.sabugo_musica_3",
        "name": "Musica 3",
        "duration": 580.882,
        "icon": null,
        "playlist": "sabugo"
    }
];
const BLOCK_ID = "meu_addon:custom_jukebox";

// Playlist list provided by the addon builder. Always includes every
// user-defined playlist, even ones with zero tracks (so "Geral" shows up
// in the in-game menu even if the user hasn't added anything to it).
const AVAILABLE_PLAYLISTS = ["Geral", "sab\u00e3o", "sabugo"];

const activeJukeboxes = new Map();
const globalController = {
    activePlaylist: AVAILABLE_PLAYLISTS[0] || "Geral",
    index: 0,
    playing: false,
    currentTrackId: null,
    startTime: 0,
    volume: 4.0,
    mode: 'sequence',  // 'sequence' or 'shuffle'
};

// Real music-disc textures shipped inside our resource pack so the
// playlist/library buttons render with colourful discs instead of the
// missing-texture grey vinyls.
const DISC_ICONS = [
    "textures/items/music_disc_lava_chicken",
    "textures/items/music_disc_precipice",
    "textures/items/music_disc_relic",
    "textures/items/music_disc_tears",
];
function discIconFor(idx) {
    return DISC_ICONS[((idx % DISC_ICONS.length) + DISC_ICONS.length) % DISC_ICONS.length];
}

function getState(block) {
    const key = `${block.location.x},${block.location.y},${block.location.z}`;
    if (!activeJukeboxes.has(key)) {
        activeJukeboxes.set(key, { 
                index: 0, 
                playing: false, 
                mode: "sequence", 
                startTime: 0, 
                volume: 4.0,
                currentTrackId: null,
                activePlaylist: AVAILABLE_PLAYLISTS[0] || "Geral",
                global: false
            });
    }
    return activeJukeboxes.get(key);
}

function getActiveTracks(playlistName) {
    return RAW_PLAYLIST.filter(t => t.playlist === playlistName);
}

// ---------- Local block sound (non-global) ----------------------
function stopLocalSound(dimension, x, y, z, trackId) {
    if (!trackId) return;
    const xF = x.toFixed(2);
    const yF = y.toFixed(2);
    const zF = z.toFixed(2);
    dimension.runCommandAsync(`stopsound @a[x=${xF},y=${yF},z=${zF},r=64] ${trackId}`);
}

function playLocalTrack(block, index) {
    const state = getState(block);
    const tracks = getActiveTracks(state.activePlaylist);
    if (tracks.length === 0) return;
    if (index < 0) index = tracks.length - 1;
    if (index >= tracks.length) index = 0;

    const track = tracks[index];
    const { x, y, z } = block.location;

    stopLocalSound(block.dimension, x, y, z, state.currentTrackId);

    const cmd = `playsound ${track.id} @a ${x.toFixed(2)} ${y.toFixed(2)} ${z.toFixed(2)} ${state.volume} 1.0`;
    block.dimension.runCommandAsync(cmd);

    state.index = index;
    state.playing = true;
    state.currentTrackId = track.id;
    state.startTime = new Date().getTime();
}

// ---------- Global broadcast ------------------------------------
function stopGlobalSound() {
    if (!globalController.currentTrackId) return;
    // stopsound @a is scope-global across dimensions, so a single call
    // silences the track for every online player.
    world.getDimension("overworld").runCommandAsync(`stopsound @a ${globalController.currentTrackId}`);
}

function playGlobalTrack(initiatorBlock, index) {
    const playlist = globalController.activePlaylist;
    const tracks = RAW_PLAYLIST.filter(t => t.playlist === playlist);
    if (tracks.length === 0) return;
    if (index < 0) index = tracks.length - 1;
    if (index >= tracks.length) index = 0;

    const track = tracks[index];

    stopGlobalSound();

    // Critical: play at EACH player's own position, not at 0,0,0 (a fixed
    // position + max_distance=64 means players in the wild can't hear it).
    // `@s ~ ~ ~` inside player.runCommandAsync = at the player themselves.
    for (const player of world.getAllPlayers()) {
        try {
            player.runCommandAsync(`playsound ${track.id} @s ~ ~ ~ ${globalController.volume} 1.0`);
        } catch (e) { /* player despawned mid-call */ }
    }

    globalController.index = index;
    globalController.playing = true;
    globalController.currentTrackId = track.id;
    globalController.startTime = new Date().getTime();

    // The block that triggered the play "drives" the auto-advance interval.
    if (initiatorBlock) {
        const state = getState(initiatorBlock);
        state.playing = true;
        state.index = index;
        state.currentTrackId = track.id;
        state.startTime = globalController.startTime;
    }
}

function nextGlobal(initiatorBlock) {
    const tracks = RAW_PLAYLIST.filter(t => t.playlist === globalController.activePlaylist);
    if (tracks.length === 0) return;
    const next = globalController.mode === 'shuffle'
        ? Math.floor(Math.random() * tracks.length)
        : (globalController.index + 1) % tracks.length;
    playGlobalTrack(initiatorBlock, next);
}

function prevGlobal(initiatorBlock) {
    const tracks = RAW_PLAYLIST.filter(t => t.playlist === globalController.activePlaylist);
    if (tracks.length === 0) return;
    const prev = (globalController.index - 1 + tracks.length) % tracks.length;
    playGlobalTrack(initiatorBlock, prev);
}

// ---------- Unified API used by the form handler ---------------
function playTrack(block, index) {
    const state = getState(block);
    if (state.global) playGlobalTrack(block, index);
    else playLocalTrack(block, index);
}

function nextTrack(block) {
    const state = getState(block);
    if (state.global) { nextGlobal(block); return; }
    const tracks = getActiveTracks(state.activePlaylist);
    if (tracks.length === 0) return;
    const next = state.mode === 'shuffle'
        ? Math.floor(Math.random() * tracks.length)
        : (state.index + 1) % tracks.length;
    playLocalTrack(block, next);
}

function prevTrack(block) {
    const state = getState(block);
    if (state.global) { prevGlobal(block); return; }
    const tracks = getActiveTracks(state.activePlaylist);
    if (tracks.length === 0) return;
    const prev = (state.index - 1 + tracks.length) % tracks.length;
    playLocalTrack(block, prev);
}

function pauseTrack(block) {
    const state = getState(block);
    if (state.global) {
        stopGlobalSound();
        globalController.playing = false;
        globalController.currentTrackId = null;
        state.playing = false;
    } else {
        const { x, y, z } = block.location;
        stopLocalSound(block.dimension, x, y, z, state.currentTrackId);
        state.playing = false;
    }
}

system.runInterval(() => {
    // Auto-advance: for each block that is "driving" playback, check if
    // its current track has ended. Works for both local and global modes
    // (in global, only the initiator block has state.playing=true).
    for (const [key, state] of activeJukeboxes) {
        if (!state.playing) continue;

        const isGlobal = state.global;
        const playlist = isGlobal ? globalController.activePlaylist : state.activePlaylist;
        const idx = isGlobal ? globalController.index : state.index;
        const tracks = RAW_PLAYLIST.filter(t => t.playlist === playlist);
        const track = tracks[idx];
        if (!track) continue;

        const elapsedSeconds = (new Date().getTime() - state.startTime) / 1000;
        if (track.duration > 0 && elapsedSeconds > track.duration + 1) {
            const coords = key.split(",").map(Number);
            try {
                const block = world.getDimension("overworld").getBlock({ x: coords[0], y: coords[1], z: coords[2] });
                if (block && block.typeId === BLOCK_ID) nextTrack(block);
                else activeJukeboxes.delete(key);
            } catch (e) { activeJukeboxes.delete(key); }
        }
    }
}, 20);

// Build a unified "view" of what's currently active on this block. In
// global mode the form shows globalController's state (so every global
// block displays the same currently-playing track); in local mode it
// shows the block's own state.
function getView(block) {
    const state = getState(block);
    if (state.global) {
        const playlist = globalController.activePlaylist;
        const tracks = RAW_PLAYLIST.filter(t => t.playlist === playlist);
        return {
            isGlobal: true,
            playlist,
            tracks,
            index: globalController.index,
            playing: globalController.playing,
            track: tracks[globalController.index],
            mode: globalController.mode,
        };
    }
    return {
        isGlobal: false,
        playlist: state.activePlaylist,
        tracks: getActiveTracks(state.activePlaylist),
        index: state.index,
        playing: state.playing,
        track: getActiveTracks(state.activePlaylist)[state.index],
        mode: state.mode,
    };
}

world.beforeEvents.worldInitialize.subscribe(initEvent => {
    initEvent.blockComponentRegistry.registerCustomComponent('meu_addon:jukebox_click', {
        onPlayerInteract: (e) => {
            const { block, player } = e;
            if (!player || player.isSneaking) return;

            const state = getState(block);
            const view = getView(block);

            const form = new ActionFormData()
                .title(view.isGlobal ? "§2Vitrola §6[GLOBAL]" : "§2Vitrola")
                .body(
                    `§fTocando agora:
` +
                    `§a${view.playing && view.track ? "♫ " + view.track.name : "§7(Parado)"}

` +
                    `§fPlaylist: §e${view.playlist}
` +
                    `§fFaixas: §7${view.tracks.length}
` +
                    `§fModo: §7${view.mode === 'shuffle' ? "Aleatório" : "Sequência"}`
                );

            if (view.playing) {
                form.button("§cPAUSAR", "textures/items/redstone_dust");
            } else {
                form.button("§aTOCAR", "textures/items/emerald");
            }

            form.button("PRÓXIMA", "textures/items/arrow");
            form.button("ANTERIOR", "textures/items/arrow");

            const iconMode = view.mode === 'shuffle' ? "textures/items/redstone_dust" : "textures/items/repeater";
            form.button(`Modo: ${view.mode === 'shuffle' ? 'ALEATÓRIO' : 'SEQUÊNCIA'}`, iconMode);

            const iconGlobal = state.global ? DISC_ICONS[0] : DISC_ICONS[2];
            form.button(`Global: ${state.global ? 'ON' : 'OFF'}`, iconGlobal);

            form.button("§lBIBLIOTECA", "textures/items/book_writable");
            form.button("§lMUDAR PLAYLIST", "textures/items/name_tag");

            system.run(() => {
                form.show(player).then((res) => {
                    if (res.canceled) return;
                    const sel = res.selection;

                    if (sel === 0) {
                        if (view.playing) {
                            pauseTrack(block);
                        } else {
                            playTrack(block, view.index);
                        }
                    }
                    else if (sel === 1) nextTrack(block);
                    else if (sel === 2) prevTrack(block);
                    else if (sel === 3) {
                        // Toggle mode on whichever controller is active.
                        if (state.global) {
                            globalController.mode = globalController.mode === 'sequence' ? 'shuffle' : 'sequence';
                            player.sendMessage(`§aModo global: ${globalController.mode}`);
                        } else {
                            state.mode = state.mode === 'sequence' ? 'shuffle' : 'sequence';
                            player.sendMessage(`§aModo: ${state.mode}`);
                        }
                    }
                    else if (sel === 4) {
                        // Toggle global ON/OFF for this block.
                        const turningOn = !state.global;
                        state.global = turningOn;
                        if (turningOn) {
                            // Adopt the global playlist on this block so the
                            // form shows what's actually broadcasting.
                            if (!globalController.activePlaylist) {
                                globalController.activePlaylist = state.activePlaylist;
                            }
                        } else {
                            // Turning OFF: just detach. Other global blocks
                            // and the broadcast keep playing.
                            state.playing = false;
                            state.currentTrackId = null;
                        }
                        player.sendMessage(`§aGlobal: ${turningOn ? 'ON' : 'OFF'}`);
                    }
                    else if (sel === 5) openListMenu(player, block);
                    else if (sel === 6) openPlaylistMenu(player, block);
                }).catch(e => console.error(e));
            });
        }
    });
});

function openListMenu(player, block) {
    const view = getView(block);
    const form = new ActionFormData().title(`§2Biblioteca: ${view.playlist}${view.isGlobal ? ' §6[GLOBAL]' : ''}`);

    if (view.tracks.length === 0) {
        form.body("§7Nenhuma faixa nessa playlist.");
        form.button("Voltar", "textures/items/arrow");
        system.run(() => form.show(player).catch(e => console.error(e)));
        return;
    }

    for (let i = 0; i < view.tracks.length; i++) {
        const t = view.tracks[i];
        const m = Math.floor(t.duration / 60);
        const s = Math.floor(t.duration % 60);
        const timeStr = `${m}:${s < 10 ? '0' : ''}${s}`;
        const icon = t.icon ? t.icon : discIconFor(i);
        form.button(`§f${t.name}
§7${timeStr}`, icon);
    }
    system.run(() => {
        form.show(player).then(res => {
            if (res.canceled) return;
            playTrack(block, res.selection);
        }).catch(e => console.error(e));
    });
}

function openPlaylistMenu(player, block) {
    const state = getState(block);
    const form = new ActionFormData().title(state.global ? "§2Escolher Playlist §6[GLOBAL]" : "§2Escolher Playlist");
    for (let i = 0; i < AVAILABLE_PLAYLISTS.length; i++) {
        const p = AVAILABLE_PLAYLISTS[i];
        const trackCount = RAW_PLAYLIST.filter(t => t.playlist === p).length;
        form.button(`§f${p}
§7${trackCount} faixa(s)`, discIconFor(i));
    }
    system.run(() => {
        form.show(player).then(res => {
            if (res.canceled) return;
            const newPlaylist = AVAILABLE_PLAYLISTS[res.selection];

            if (state.global) {
                // Switching the global playlist affects every global block.
                stopGlobalSound();
                globalController.activePlaylist = newPlaylist;
                globalController.index = 0;
                globalController.playing = false;
                globalController.currentTrackId = null;
                state.playing = false;
                state.currentTrackId = null;
                player.sendMessage(`§aPlaylist global: ${newPlaylist}`);
            } else {
                const { x, y, z } = block.location;
                stopLocalSound(block.dimension, x, y, z, state.currentTrackId);
                state.activePlaylist = newPlaylist;
                state.index = 0;
                state.playing = false;
                state.currentTrackId = null;
                player.sendMessage(`§aPlaylist: ${newPlaylist}`);
            }
        }).catch(e => console.error(e));
    });
}

world.afterEvents.playerBreakBlock.subscribe((event) => {
    const { block, brokenBlockPermutation } = event;
    if (brokenBlockPermutation.type.id === BLOCK_ID) {
        const key = `${block.location.x},${block.location.y},${block.location.z}`;
        const state = activeJukeboxes.get(key);
        if (state && state.currentTrackId && !state.global) {
            stopLocalSound(
                event.player ? event.player.dimension : block.dimension,
                block.location.x, block.location.y, block.location.z,
                state.currentTrackId
            );
        }
        activeJukeboxes.delete(key);
    }
});
