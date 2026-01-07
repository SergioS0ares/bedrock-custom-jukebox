
import { world, system } from "@minecraft/server";
import { ActionFormData } from "@minecraft/server-ui";

const PLAYLIST = [
    {
        "id": "custom.jukebox.grimm_hollow_knight_the_grimm_troupe__christopher_larkin_youtube",
        "name": "Grimm (Hollow Knight The Grimm Troupe) - Christopher Larkin (Youtube)",
        "duration": 138.65795,
        "icon": null
    },
    {
        "id": "custom.jukebox.mc_orsen__warning_speed_up_extended_mix__bass_boosted__rocky_tiktok_edit__olderbrotheradvice_youtube",
        "name": "Mc Orsen - Warning (Speed Up) Extended Mix - Bass Boosted - Rocky Tiktok Edit - Olderbrotheradvice (Youtube)",
        "duration": 252.47345,
        "icon": null
    },
    {
        "id": "custom.jukebox.musica1",
        "name": "Musica1",
        "duration": 289.181315,
        "icon": null
    }
];
const BLOCK_ID = "meu_addon:custom_jukebox";

// Mapa de estado
const activeJukeboxes = new Map();

function getState(block) {
    const key = `${block.location.x},${block.location.y},${block.location.z}`;
    if (!activeJukeboxes.has(key)) {
        activeJukeboxes.set(key, { index: 0, playing: false, mode: "sequence", startTime: 0, volume: 4.0 });
    }
    return activeJukeboxes.get(key);
}

function stopSound(dimension, x, y, z) {
    const xF = x.toFixed(2);
    const yF = y.toFixed(2);
    const zF = z.toFixed(2);
    dimension.runCommandAsync(`stopsound @a[x=${xF},y=${yF},z=${zF},r=64]`);
}

function playTrack(block, index) {
    const state = getState(block);
    if (index < 0) index = PLAYLIST.length - 1;
    if (index >= PLAYLIST.length) index = 0;

    const track = PLAYLIST[index];
    const x = block.location.x;
    const y = block.location.y;
    const z = block.location.z;

    stopSound(block.dimension, x, y, z);
    
    const xF = x.toFixed(2);
    const yF = y.toFixed(2);
    const zF = z.toFixed(2);
    
    const cmd = `playsound ${track.id} @a ${xF} ${yF} ${zF} ${state.volume} 1.0`;
    block.dimension.runCommandAsync(cmd);

    state.index = index;
    state.playing = true;
    state.startTime = new Date().getTime();
}

function nextTrack(block) {
    const state = getState(block);
    let nextIndex = 0;
    if (state.mode === 'shuffle') {
        nextIndex = Math.floor(Math.random() * PLAYLIST.length);
    } else {
        nextIndex = state.index + 1;
        if (nextIndex >= PLAYLIST.length) nextIndex = 0;
    }
    playTrack(block, nextIndex);
}

// Loop Autoplay
system.runInterval(() => {
    for (const [key, state] of activeJukeboxes) {
        if (state.playing) {
            const track = PLAYLIST[state.index];
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

// --- INTERFACE CORRIGIDA ---
world.beforeEvents.worldInitialize.subscribe(initEvent => {
    initEvent.blockComponentRegistry.registerCustomComponent('meu_addon:jukebox_click', {
        onPlayerInteract: (e) => {
            const { block, player } = e;
            if (!player || player.isSneaking) return;

            const state = getState(block);
            const currentTrack = PLAYLIST[state.index];
            
            const form = new ActionFormData()
                .title("§2Music Player") // Título alterado
                .body(
                    `§fTocando agora:\n` +
                    `§a${state.playing ? "♫ " + currentTrack.name : "§7(Parado)"}\n\n` +
                    `§fModo: §7${state.mode === 'shuffle' ? "Aleatório" : "Sequência"}`
                );

            // Botões de Controle com Ícones de ITENS (Confiáveis)
            if (state.playing) {
                // Pausar com Redstone (Vermelho)
                form.button("§cPAUSAR", "textures/items/redstone_dust");
            } else {
                // Tocar com Esmeralda (Verde)
                form.button("§aTOCAR", "textures/items/emerald");
            }
            
            // Próxima/Anterior com Flechas
            form.button("PRÓXIMA", "textures/items/arrow");
            form.button("ANTERIOR", "textures/items/arrow");
            
            const iconMode = state.mode === 'shuffle' ? "textures/items/redstone_dust" : "textures/items/repeater";
            form.button(`Modo: ${state.mode.toUpperCase()}`, iconMode);

            form.button("§lBIBLIOTECA", "textures/items/book_writable");

            system.run(() => {
                form.show(player).then((res) => {
                    if (res.canceled) return;
                    const sel = res.selection;

                    if (sel === 0) { 
                        if (state.playing) { 
                            stopSound(block.dimension, block.location.x, block.location.y, block.location.z); 
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
                        player.sendMessage(`§aModo: ${state.mode}`);
                    }
                    else if (sel === 4) openListMenu(player, block);
                }).catch(e => console.error(e));
            });
        }
    });
});

function openListMenu(player, block) {
    const form = new ActionFormData().title("§2Biblioteca");
    for (const t of PLAYLIST) {
        const m = Math.floor(t.duration / 60);
        const s = Math.floor(t.duration % 60);
        const timeStr = `${m}:${s < 10 ? '0' : ''}${s}`;
        
        const icon = t.icon ? t.icon : "textures/items/record_13";
        form.button(`§f${t.name}\n§7${timeStr}`, icon);
    }
    system.run(() => {
        form.show(player).then(res => {
            if (res.canceled) return;
            playTrack(block, res.selection);
        });
    });
}

world.afterEvents.playerBreakBlock.subscribe((event) => {
    const { block, brokenBlockPermutation } = event;
    if (brokenBlockPermutation.type.id === BLOCK_ID) {
        const key = `${block.location.x},${block.location.y},${block.location.z}`;
        activeJukeboxes.delete(key);
        stopSound(event.player ? event.player.dimension : block.dimension, block.location.x, block.location.y, block.location.z);
    }
});
