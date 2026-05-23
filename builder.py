import os
import re
import json
import zipfile
import subprocess
import shutil
import uuid
import time


def _slug(name):
    """Mirror of main.py's playlist_slug. Lowercase + underscores + ASCII."""
    s = (name or "Geral").strip().lower().replace(" ", "_")
    return re.sub(r"[^a-z0-9_]", "", s) or "geral"

# --- CONFIGURAÇÕES ---
BASE_DIR = os.path.abspath(os.getcwd())
NOME_ADDON = "Bedrock_Custom_Jukebox"

PASTA_SOURCE = os.path.join(BASE_DIR, "addon_source")
PASTA_MUSICA = os.path.join(BASE_DIR, "user_music")

# Prefer ./ffmpeg.exe at the project root; otherwise fall back to whatever
# is on PATH (so `winget install Gyan.FFmpeg` works without copying binaries).
def _resolve_tool(local_name, path_name):
    local = os.path.join(BASE_DIR, local_name)
    if os.path.exists(local):
        return local
    found = shutil.which(path_name)
    return found if found else local  # return local path so error message stays useful

FFMPEG_EXE = _resolve_tool("ffmpeg.exe", "ffmpeg")
FFPROBE_EXE = _resolve_tool("ffprobe.exe", "ffprobe")
PASTA_CACHE_AUDIO = os.path.join(BASE_DIR, "_audio_cache_")
# Caminhos internos
SUBPASTA_AUDIO = "sounds/jukebox"
SUBPASTA_ICONES = "textures/jukebox_icons"
PASTA_DEFINICAO = "sounds"

MEU_BLOCO_ID = "meu_addon:custom_jukebox"
NOME_DISPLAY_BLOCO = "Vitrola"
CHAVE_TEXTURA_TOP = "vitrola_top"
CHAVE_TEXTURA_SIDE = "vitrola_side"
COMPONENT_ID = "meu_addon:jukebox_click"

# Optional input: a JSON file with the full list of user-defined playlist
# names, written by main.py before invoking build. Lets us show empty
# playlists (like an unused "Geral") in the in-game menu.
PLAYLISTS_INPUT_FILE = os.path.join(BASE_DIR, "_playlists_input.json")
# Optional input: a PNG used as the block texture (all faces).
BLOCK_TEXTURE_SOURCE = os.path.join(BASE_DIR, "images", "jukeboxColorida.png")

def criar_pasta_se_nao_existir(caminho):
    if not os.path.exists(caminho):
        try:
            os.makedirs(caminho, exist_ok=True)
        except OSError:
            time.sleep(0.1)
            os.makedirs(caminho, exist_ok=True)

def salvar_arquivo_seguro(caminho_arquivo, conteudo, is_json=False):
    pasta_pai = os.path.dirname(caminho_arquivo)
    criar_pasta_se_nao_existir(pasta_pai)
    with open(caminho_arquivo, "w", encoding='utf-8') as f:
        if is_json:
            json.dump(conteudo, f, indent=4)
        else:
            f.write(conteudo)
JS_TEMPLATE = """
import { world, system } from "@minecraft/server";
import { ActionFormData, ModalFormData } from "@minecraft/server-ui";

const RAW_PLAYLIST = %PLAYLIST_JSON%;
const BLOCK_ID = "%BLOCK_ID%";

// Playlist list provided by the addon builder. Always includes every
// user-defined playlist, even ones with zero tracks (so "Geral" shows up
// in the in-game menu even if the user hasn't added anything to it).
const AVAILABLE_PLAYLISTS = %AVAILABLE_PLAYLISTS_JSON%;

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
    initEvent.blockComponentRegistry.registerCustomComponent('%COMPONENT_ID%', {
        onPlayerInteract: (e) => {
            const { block, player } = e;
            if (!player || player.isSneaking) return;

            const state = getState(block);
            const view = getView(block);

            const form = new ActionFormData()
                .title(view.isGlobal ? "§2Vitrola §6[GLOBAL]" : "§2Vitrola")
                .body(
                    `§fTocando agora:\n` +
                    `§a${view.playing && view.track ? "♫ " + view.track.name : "§7(Parado)"}\n\n` +
                    `§fPlaylist: §e${view.playlist}\n` +
                    `§fFaixas: §7${view.tracks.length}\n` +
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
        form.button(`§f${t.name}\n§7${timeStr}`, icon);
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
        form.button(`§f${p}\n§7${trackCount} faixa(s)`, discIconFor(i));
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
"""

def verificar_ferramentas():
    if not os.path.exists(FFMPEG_EXE) and not shutil.which(FFMPEG_EXE):
        print("ERRO: ffmpeg não encontrado.")
        print("  Opção 1: coloque ffmpeg.exe e ffprobe.exe na raiz do projeto.")
        print("  Opção 2 (Windows): winget install Gyan.FFmpeg")
        print("                     (depois reinicie o terminal/uvicorn)")
        return False
    return True

def get_duration(file_path):
    if not os.path.exists(FFPROBE_EXE): return 0
    try:
        cmd = [FFPROBE_EXE, "-v", "error", "-show_entries", "format=duration", "-of", "default=noprint_wrappers=1:nokey=1", file_path]
        result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, encoding='utf-8')
        if result.stdout: return float(result.stdout.strip())
        return 0
    except: return 0

def gerar_lang():
    path_en = os.path.join(PASTA_SOURCE, "RP", "texts", "en_US.lang")
    path_pt = os.path.join(PASTA_SOURCE, "RP", "texts", "pt_BR.lang")
    path_json = os.path.join(PASTA_SOURCE, "RP", "texts", "languages.json")
    
    conteudo = f"tile.{MEU_BLOCO_ID}.name={NOME_DISPLAY_BLOCO}"
    
    salvar_arquivo_seguro(path_en, conteudo)
    salvar_arquivo_seguro(path_pt, conteudo)
    salvar_arquivo_seguro(path_json, ["en_US", "pt_BR"], is_json=True)

def gerar_arquivos_base():
    # 1. Behavior
    BLOCK_BP = {
        "format_version": "1.21.0",
        "minecraft:block": {
            "description": {
                "identifier": MEU_BLOCO_ID,
                "menu_category": { "category": "items", "group": "itemGroup.name.items" }
            },
            "components": {
                "minecraft:destructible_by_mining": { "seconds_to_destroy": 1.0 },
                "minecraft:geometry": "minecraft:geometry.full_block",
                "minecraft:material_instances": {
                    "*": { "texture": CHAVE_TEXTURA_SIDE, "render_method": "opaque" },
                    "up": { "texture": CHAVE_TEXTURA_TOP, "render_method": "opaque" }
                },
                "minecraft:custom_components": [ COMPONENT_ID ]
            }
        }
    }
    salvar_arquivo_seguro(os.path.join(PASTA_SOURCE, "BP", "blocks", "jukebox.json"), BLOCK_BP, is_json=True)

    # 2. Resource — atlas maps our texture keys to the vanilla jukebox
    # texture paths. We do NOT ship any jukebox_*.png in the RP, so the
    # engine resolves these from the player's built-in vanilla atlas and
    # the block ends up looking like a regular jukebox.
    terrain_texture = {
        "resource_pack_name": "jukebox_rp",
        "texture_name": "atlas.terrain",
        "padding": 8,
        "num_mip_levels": 4,
        "texture_data": {
            CHAVE_TEXTURA_SIDE: { "textures": "textures/blocks/jukebox_side" },
            CHAVE_TEXTURA_TOP:  { "textures": "textures/blocks/jukebox_top" },
        }
    }
    salvar_arquivo_seguro(os.path.join(PASTA_SOURCE, "RP", "textures", "terrain_texture.json"), terrain_texture, is_json=True)

    criar_pasta_se_nao_existir(os.path.join(PASTA_SOURCE, "RP", "textures", "jukebox_icons"))

    # Manifests
    uuid_bp, uuid_rp = str(uuid.uuid4()), str(uuid.uuid4())

    bp_manifest = {
        "format_version": 2,
        "header": { "name": "Vitrola BP", "description": "Custom jukebox addon with playlists and global broadcast.", "uuid": uuid_bp, "version": [1, 0, 0], "min_engine_version": [1, 21, 0] },
        "modules": [ { "type": "data", "uuid": str(uuid.uuid4()), "version": [1, 0, 0] }, { "type": "script", "language": "javascript", "uuid": str(uuid.uuid4()), "version": [1, 0, 0], "entry": "scripts/main.js" } ],
        "dependencies": [ { "module_name": "@minecraft/server", "version": "1.12.0" }, { "module_name": "@minecraft/server-ui", "version": "1.2.0" }, { "uuid": uuid_rp, "version": [1, 0, 0] } ]
    }
    rp_manifest = {
        "format_version": 2,
        "header": { "name": "Vitrola RP", "description": "Textures + sounds for the custom jukebox.", "uuid": uuid_rp, "version": [1, 0, 0], "min_engine_version": [1, 21, 0] },
        "modules": [ { "type": "resources", "uuid": str(uuid.uuid4()), "version": [1, 0, 0] } ]
    }

    salvar_arquivo_seguro(os.path.join(PASTA_SOURCE, "BP", "manifest.json"), bp_manifest, is_json=True)
    salvar_arquivo_seguro(os.path.join(PASTA_SOURCE, "RP", "manifest.json"), rp_manifest, is_json=True)

    # Pack icon — shows up in the Minecraft addon list. Reuse the same
    # colourful jukebox PNG that's already the block texture.
    if os.path.exists(BLOCK_TEXTURE_SOURCE):
        for pack in ("BP", "RP"):
            shutil.copy(BLOCK_TEXTURE_SOURCE, os.path.join(PASTA_SOURCE, pack, "pack_icon.png"))

    # Music disc icons used by the in-game playlist/library buttons.
    # We ship them in the RP at vanilla paths so they look right on every
    # client (even older versions that don't have these discs).
    disc_src_dir = os.path.join(BASE_DIR, "images")
    disc_dst_dir = os.path.join(PASTA_SOURCE, "RP", "textures", "items")
    criar_pasta_se_nao_existir(disc_dst_dir)
    for fname in ("music_disc_lava_chicken.png", "music_disc_precipice.png",
                  "music_disc_relic.png", "music_disc_tears.png"):
        src = os.path.join(disc_src_dir, fname)
        if os.path.exists(src):
            shutil.copy(src, os.path.join(disc_dst_dir, fname))

# Music discs accepted as the "D" ingredient. We emit one recipe file per
# disc because vanilla Bedrock has no `minecraft:music_discs` tag.
MUSIC_DISCS = [
    "minecraft:music_disc_13",
    "minecraft:music_disc_cat",
    "minecraft:music_disc_blocks",
    "minecraft:music_disc_chirp",
    "minecraft:music_disc_far",
    "minecraft:music_disc_mall",
    "minecraft:music_disc_mellohi",
    "minecraft:music_disc_stal",
    "minecraft:music_disc_strad",
    "minecraft:music_disc_ward",
    "minecraft:music_disc_11",
    "minecraft:music_disc_wait",
    "minecraft:music_disc_pigstep",
    "minecraft:music_disc_otherside",
    "minecraft:music_disc_5",
    "minecraft:music_disc_relic",
    "minecraft:music_disc_creator",
    "minecraft:music_disc_creator_music_box",
    "minecraft:music_disc_precipice",
    "minecraft:music_disc_lava_chicken",
    "minecraft:music_disc_tears",
]


def gerar_recipe():
    """Emit one shaped recipe per music disc. Pattern:
         P D P     P = any plank
         P J P     D = music disc (varies per recipe)
         N _ N     J = vanilla jukebox, N = iron nugget, _ = empty
    """
    for disc in MUSIC_DISCS:
        slug = disc.split(":")[-1]
        path = os.path.join(PASTA_SOURCE, "BP", "recipes", f"jukebox_{slug}.json")
        recipe = {
            "format_version": "1.21.0",
            "minecraft:recipe_shaped": {
                "description": { "identifier": f"{MEU_BLOCO_ID}_recipe_{slug}" },
                "tags": [ "crafting_table" ],
                "pattern": [
                    "PDP",
                    "PJP",
                    "N N"
                ],
                "key": {
                    "P": { "tag": "minecraft:planks" },
                    "J": { "item": "minecraft:jukebox" },
                    "N": { "item": "minecraft:iron_nugget" },
                    "D": { "item": disc }
                },
                "unlock": [ { "context": "AlwaysUnlocked" } ],
                "result": { "item": MEU_BLOCO_ID }
            }
        }
        salvar_arquivo_seguro(path, recipe, is_json=True)
    print(f"  emitted {len(MUSIC_DISCS)} disc recipes (planks + jukebox + iron nuggets)")

def main():
    print("--- GERANDO BEDROCK CUSTOM JUKEBOX ---")
    if not verificar_ferramentas(): return
    
    if os.path.exists(PASTA_SOURCE):
        try: shutil.rmtree(PASTA_SOURCE); time.sleep(0.5)
        except: pass

    if os.path.exists(PASTA_CACHE_AUDIO): shutil.rmtree(PASTA_CACHE_AUDIO)
    os.makedirs(PASTA_CACHE_AUDIO, exist_ok=True)

    gerar_arquivos_base()
    gerar_lang()
    gerar_recipe()
    playlist_data = []
    sound_defs = { "format_version": "1.14.0", "sound_definitions": {} }

    # Load the user's playlist names so we can preserve their original
    # casing (e.g. "joelma" stays as "joelma" — without this, the folder
    # name on disk is `joelma` lowercase and we'd Title-Case it to
    # "Joelma", which mismatches what the in-game menu shows).
    user_playlists = []
    if os.path.exists(PLAYLISTS_INPUT_FILE):
        try:
            with open(PLAYLISTS_INPUT_FILE, "r", encoding="utf-8") as f:
                user_playlists = [str(p) for p in json.load(f) if p]
        except Exception as e:
            print(f"  WARN: could not read {PLAYLISTS_INPUT_FILE}: {e}")
    slug_to_name = {_slug(p): p for p in user_playlists}
    slug_to_name.setdefault("geral", "Geral")

    if not os.path.exists(PASTA_MUSICA): os.makedirs(PASTA_MUSICA, exist_ok=True)
    print("Processando faixas e playlists...")

    for root, dirs, files in os.walk(PASTA_MUSICA):
        nome_pasta = os.path.basename(root)
        if nome_pasta == os.path.basename(PASTA_MUSICA):
            playlist_slug = "geral"
        else:
            playlist_slug = nome_pasta.lower().replace(" ", "_")
        # Prefer the user-supplied name; fall back to a title-cased folder.
        playlist_name = slug_to_name.get(playlist_slug, nome_pasta.replace("_", " ").title())

        arquivos_audio = [f for f in files if f.lower().endswith(('.mp3','.wav','.ogg','.m4a','.flac'))]
        for f in arquivos_audio:
            base_name = os.path.splitext(f)[0]
            name_clean_base = "".join([c for c in base_name.lower().replace(" ", "_") if c.isalnum() or c == "_"])
            name_clean = f"{playlist_slug}_{name_clean_base}" if playlist_slug != "geral" else name_clean_base

            src = os.path.join(root, f)
            dst = os.path.join(PASTA_CACHE_AUDIO, f"{name_clean}.ogg")
            # Capture stderr so a busted conversion (corrupt file, weird codec,
            # path encoding issue) shows up in the build log instead of being
            # silently dropped.
            result = subprocess.run(
                [FFMPEG_EXE, '-y', '-i', src, '-vn', '-ac', '1', '-acodec', 'libvorbis', dst],
                stdout=subprocess.PIPE, stderr=subprocess.PIPE,
            )
            if result.returncode != 0 or not os.path.exists(dst):
                err = result.stderr.decode('utf-8', errors='replace').strip()
                tail = err.splitlines()[-1] if err else "(no stderr)"
                print(f"  FFMPEG FAILED for {f} ({playlist_name}): {tail}")
                continue

            icon_path = None
            for ext in ['.png', '.jpg', '.jpeg']:
                img_src = os.path.join(root, base_name + ext)
                if os.path.exists(img_src):
                    img_dst_name = f"{name_clean}.png"
                    img_dst_path = os.path.join(PASTA_SOURCE, "RP", "textures", "jukebox_icons", img_dst_name)
                    if ext == '.png':
                        shutil.copy(img_src, img_dst_path)
                    else:
                        subprocess.run([FFMPEG_EXE, '-y', '-i', img_src, img_dst_path], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
                    icon_path = f"textures/jukebox_icons/{name_clean}"
                    break

            sound_id = f"custom.jukebox.{name_clean}"
            playlist_data.append({ 
                "id": sound_id, 
                "name": base_name.replace("_", " ").title(), 
                "duration": get_duration(src),
                "icon": icon_path,
                "playlist": playlist_name
            })

            sound_defs["sound_definitions"][sound_id] = {
                "category": "record", "min_distance": 4.0, "max_distance": 64.0, 
                "sounds": [ { "name": f"{SUBPASTA_AUDIO}/{name_clean}", "stream": True, "load_on_low_memory": True } ]
            }
            print(f"OK: {os.path.relpath(src, BASE_DIR)}")

    path_sounds = os.path.join(PASTA_SOURCE, "RP", PASTA_DEFINICAO, "sound_definitions.json")
    salvar_arquivo_seguro(path_sounds, sound_defs, is_json=True)

    # Read the user's full list of playlists (so empty ones still show
    # up in the in-game playlist picker). Fall back to whatever playlists
    # actually have tracks.
    track_playlists = list(dict.fromkeys(t["playlist"] for t in playlist_data))
    available_playlists = list(track_playlists)
    if os.path.exists(PLAYLISTS_INPUT_FILE):
        try:
            with open(PLAYLISTS_INPUT_FILE, "r", encoding="utf-8") as f:
                from_user = json.load(f)
            for p in from_user:
                if p and p not in available_playlists:
                    available_playlists.append(p)
        except Exception as e:
            print(f"  WARN: could not read {PLAYLISTS_INPUT_FILE}: {e}")
    if "Geral" not in available_playlists:
        available_playlists.insert(0, "Geral")

    path_js = os.path.join(PASTA_SOURCE, "BP", "scripts", "main.js")
    js_content = JS_TEMPLATE \
        .replace("%PLAYLIST_JSON%", json.dumps(playlist_data, indent=4)) \
        .replace("%AVAILABLE_PLAYLISTS_JSON%", json.dumps(available_playlists)) \
        .replace("%BLOCK_ID%", MEU_BLOCO_ID) \
        .replace("%COMPONENT_ID%", COMPONENT_ID)
    salvar_arquivo_seguro(path_js, js_content)

    out = os.path.join(BASE_DIR, f"{NOME_ADDON}.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(PASTA_SOURCE):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PASTA_SOURCE)
                z.write(abs_path, rel_path)
        for ogg in os.listdir(PASTA_CACHE_AUDIO):
            z.write(os.path.join(PASTA_CACHE_AUDIO, ogg), f"RP/{SUBPASTA_AUDIO}/{ogg}")

    print(f"--- SUCESSO! ---")
    print(f"Arquivo gerado: {out}")
    print("Lembre-se de deletar a versão antiga no Minecraft antes de instalar esta.")

if __name__ == "__main__":
    main()