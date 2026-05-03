
import { world, system } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";

const RAW_PLAYLIST = [
    {
        "id": "custom.jukebox.grimm_hollow_knight_the_grimm_troupe__christopher_larkin_youtube",
        "name": "Grimm (Hollow Knight The Grimm Troupe) - Christopher Larkin (Youtube)",
        "duration": 138.65795,
        "icon": null,
        "playlist": "Geral"
    },
    {
        "id": "custom.jukebox.mc_orsen__warning_speed_up_extended_mix__bass_boosted__rocky_tiktok_edit__olderbrotheradvice_youtube",
        "name": "Mc Orsen - Warning (Speed Up) Extended Mix - Bass Boosted - Rocky Tiktok Edit - Olderbrotheradvice (Youtube)",
        "duration": 252.47345,
        "icon": null,
        "playlist": "Geral"
    },
    {
        "id": "custom.jukebox.musica1",
        "name": "Musica1",
        "duration": 289.181315,
        "icon": null,
        "playlist": "Geral"
    }
];
const BLOCK_ID = "meu_addon:custom_jukebox";

// Descobrir todas as playlists disponíveis
const AVAILABLE_PLAYLISTS = [...new Set(RAW_PLAYLIST.map(t => t.playlist))];

const activeJukeboxes = new Map();
const globalController = { activePlaylist: AVAILABLE_PLAYLISTS[0] || "Geral", index: 0, playing: false, currentTrackId: null, startTime: 0, volume: 4.0 };

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

function stopSound(dimension, x, y, z, trackId) {
    if (!trackId) return;
    const xF = x.toFixed(2);
    const yF = y.toFixed(2);
    const zF = z.toFixed(2);
    dimension.runCommandAsync(`stopsound @a[x=${xF},y=${yF},z=${zF},r=64] ${trackId}`);
}

function playTrack(block, index) {
    const state = getState(block);
    const tracks = getActiveTracks(state.activePlaylist);
    
    if (tracks.length === 0) return;
    if (index < 0) index = tracks.length - 1;
    if (index >= tracks.length) index = 0;

    const track = tracks[index];
    const x = block.location.x;
    const y = block.location.y;
    const z = block.location.z;

    // Para a música anterior DESTE bloco, se houver
    stopSound(block.dimension, x, y, z, state.currentTrackId);
    // Se estiver em modo global, delega ao controlador global
    if (state.global) { playGlobalTrack(block, index); return; }
    
    const xF = x.toFixed(2);
    const yF = y.toFixed(2);
    const zF = z.toFixed(2);
    
    const cmd = `playsound ${track.id} @a ${xF} ${yF} ${zF} ${state.volume} 1.0`;
    block.dimension.runCommandAsync(cmd);

    state.index = index;
    state.playing = true;
    state.currentTrackId = track.id;
    state.startTime = new Date().getTime();
}

function stopOtherGlobal(block) {
    const myKey = `${block.location.x},${block.location.y},${block.location.z}`;
    for (const [key, st] of activeJukeboxes) {
        if (key === myKey) continue;
        if (st.global && st.currentTrackId) {
            const coords = key.split(",").map(Number);
            try {
                const dim = world.getDimension("overworld");
                dim.runCommandAsync(`stopsound @a[x=${coords[0].toFixed(2)},y=${coords[1].toFixed(2)},z=${coords[2].toFixed(2)},r=64] ${st.currentTrackId}`);
            } catch (e) { }
            st.playing = false;
            st.currentTrackId = null;
        }
    }
}

function nextTrack(block) {
    const state = getState(block);
    const tracks = getActiveTracks(state.activePlaylist);
    let nextIndex = 0;
    
    if (state.mode === 'shuffle') {
        nextIndex = Math.floor(Math.random() * tracks.length);
    } else {
        nextIndex = state.index + 1;
        if (nextIndex >= tracks.length) nextIndex = 0;
    }
    playTrack(block, nextIndex);
}

function playGlobalTrack(block, index) {
    const state = getState(block);
    const tracks = getActiveTracks(state.activePlaylist);
    if (tracks.length === 0) return;
    if (index < 0) index = tracks.length - 1;
    if (index >= tracks.length) index = 0;

    const track = tracks[index];
    // Stop previous global track
    if (globalController.currentTrackId) {
        world.getDimension("overworld").runCommandAsync(`stopsound @a ${globalController.currentTrackId}`);
    }
    // Play new global track to all players
    world.getDimension("overworld").runCommandAsync(`playsound ${track.id} @a 0 0 0 ${globalController.volume} 1.0`);

    globalController.activePlaylist = state.activePlaylist;
    globalController.index = index;
    globalController.playing = true;
    globalController.currentTrackId = track.id;
    globalController.startTime = new Date().getTime();

    // Update local state for this block
    state.index = index;
    state.playing = true;
    state.currentTrackId = track.id;
    state.startTime = globalController.startTime;
}

function nextGlobal() {
    const playlist = globalController.activePlaylist;
    const tracks = RAW_PLAYLIST.filter(t => t.playlist === playlist);
    if (!tracks || tracks.length === 0) return;
    let nextIndex = globalController.index + 1;
    if (nextIndex >= tracks.length) nextIndex = 0;
    // Find any block that is global to use as context (optional)
    let block = null;
    for (const [k, s] of activeJukeboxes) { if (s.global) { const coords = k.split(",").map(Number); try { block = world.getDimension("overworld").getBlock({ x: coords[0], y: coords[1], z: coords[2] }); break; } catch(e){} } }
    if (block) playGlobalTrack(block, nextIndex);
}

function stopGlobal() {
    if (!globalController.currentTrackId) return;
    world.getDimension("overworld").runCommandAsync(`stopsound @a ${globalController.currentTrackId}`);
    globalController.playing = false;
    globalController.currentTrackId = null;
}

system.runInterval(() => {
    for (const [key, state] of activeJukeboxes) {
        if (state.playing) {
            const tracks = getActiveTracks(state.activePlaylist);
            const track = tracks[state.index];
            if (!track) continue;
            
            const now = new Date().getTime();
            const elapsedSeconds = (now - state.startTime) / 1000;
            
            if (track.duration > 0 && elapsedSeconds > track.duration + 1) {
                const coords = key.split(",").map(Number);
                try {
                    const block = world.getDimension("overworld").getBlock({ x: coords[0], y: coords[1], z: coords[2] });
                    if (block && block.typeId === BLOCK_ID) nextTrack(block);
                    else activeJukeboxes.delete(key);
                } catch (e) { activeJukeboxes.delete(key); }
            }
        }
    }
}, 20);

world.beforeEvents.worldInitialize.subscribe(initEvent => {
    initEvent.blockComponentRegistry.registerCustomComponent('meu_addon:jukebox_click', {
        onPlayerInteract: (e) => {
            const { block, player } = e;
            if (!player || player.isSneaking) return;

            const state = getState(block);
            const tracks = getActiveTracks(state.activePlaylist);
            const currentTrack = tracks[state.index];
            
            const form = new ActionFormData()
                .title("§2Music Player")
                .body(
                    `§fTocando agora:
` +
                    `§a${state.playing && currentTrack ? "♫ " + currentTrack.name : "§7(Parado)"}

` +
                    `§fPlaylist: §e${state.activePlaylist}
` +
                    `§fModo: §7${state.mode === 'shuffle' ? "Aleatório" : "Sequência"}`
                );

            if (state.playing) {
                form.button("§cPAUSAR", "textures/items/redstone_dust");
            } else {
                form.button("§aTOCAR", "textures/items/emerald");
            }
            
            form.button("PRÓXIMA", "textures/items/arrow");
            form.button("ANTERIOR", "textures/items/arrow");
            
            const iconMode = state.mode === 'shuffle' ? "textures/items/redstone_dust" : "textures/items/repeater";
            form.button(`Modo: ${state.mode.toUpperCase()}`, iconMode);

            const iconGlobal = state.global ? "textures/items/record_11" : "textures/items/record_13";
            form.button(`Global: ${state.global ? 'ON' : 'OFF'}`, iconGlobal);

            form.button("§lBIBLIOTECA", "textures/items/book_writable");
            form.button("§lMUDAR PLAYLIST", "textures/items/name_tag");

            system.run(() => {
                form.show(player).then((res) => {
                    if (res.canceled) return;
                    const sel = res.selection;

                    if (sel === 0) { 
                        if (state.playing) { 
                            stopSound(block.dimension, block.location.x, block.location.y, block.location.z, state.currentTrackId); 
                            state.playing = false; 
                        } else { 
                            playTrack(block, state.index); 
                        }
                    }
                    else if (sel === 1) nextTrack(block);
                    else if (sel === 2) { 
                        let prev = state.index - 1;
                        playTrack(block, prev);
                    }
                    else if (sel === 3) { 
                        state.mode = state.mode === 'sequence' ? 'shuffle' : 'sequence';
                        player.sendMessage(`§aModo alterado para: ${state.mode}`);
                    }
                    else if (sel === 4) { // Global toggle
                        state.global = !state.global;
                        player.sendMessage(`§aGlobal: ${state.global ? 'ON' : 'OFF'}`);
                    }
                    else if (sel === 5) openListMenu(player, block, state);
                    else if (sel === 6) openPlaylistMenu(player, block, state);
                }).catch(e => console.error(e));
            });
        }
    });
});

function openListMenu(player, block, state) {
    const tracks = getActiveTracks(state.activePlaylist);
    const form = new ActionFormData().title(`§2Biblioteca: ${state.activePlaylist}`);
    
    for (const t of tracks) {
        const m = Math.floor(t.duration / 60);
        const s = Math.floor(t.duration % 60);
        const timeStr = `${m}:${s < 10 ? '0' : ''}${s}`;
        const icon = t.icon ? t.icon : "textures/items/record_13";
        form.button(`§f${t.name}
§7${timeStr}`, icon);
    }
    system.run(() => {
        form.show(player).then(res => {
            if (res.canceled) return;
            playTrack(block, res.selection);
        });
    });
}

function openPlaylistMenu(player, block, state) {
    const form = new ActionFormData().title("§2Escolher Playlist");
    for (const p of AVAILABLE_PLAYLISTS) {
        form.button(`§f${p}`, "textures/items/record_11");
    }
    system.run(() => {
        form.show(player).then(res => {
            if (res.canceled) return;
            
            if (state.playing) {
                stopSound(block.dimension, block.location.x, block.location.y, block.location.z, state.currentTrackId);
            }
            
            state.activePlaylist = AVAILABLE_PLAYLISTS[res.selection];
            state.index = 0;
            state.playing = false;
            player.sendMessage(`§aPlaylist alterada para: ${state.activePlaylist}`);
        });
    });
}

world.afterEvents.playerBreakBlock.subscribe((event) => {
    const { block, brokenBlockPermutation } = event;
    if (brokenBlockPermutation.type.id === BLOCK_ID) {
        const key = `${block.location.x},${block.location.y},${block.location.z}`;
        const state = activeJukeboxes.get(key);
        if (state && state.currentTrackId) {
            stopSound(event.player ? event.player.dimension : block.dimension, block.location.x, block.location.y, block.location.z, state.currentTrackId);
        }
        activeJukeboxes.delete(key);
    }
});
