import os
import json
import zipfile
import subprocess
import shutil
import uuid
import time

# --- CONFIGURAÇÕES ---
BASE_DIR = os.path.abspath(os.getcwd())
NOME_ADDON = "Music_Player_Final_Fixed"

PASTA_SOURCE = os.path.join(BASE_DIR, "addon_source")
PASTA_MUSICA = os.path.join(BASE_DIR, "user_music")
FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")
FFPROBE_EXE = os.path.join(BASE_DIR, "ffprobe.exe")
PASTA_CACHE_AUDIO = os.path.join(BASE_DIR, "_audio_cache_")
# Caminhos internos
SUBPASTA_AUDIO = "sounds/jukebox"
SUBPASTA_ICONES = "textures/jukebox_icons"
PASTA_DEFINICAO = "sounds"

MEU_BLOCO_ID = "meu_addon:custom_jukebox"
NOME_DISPLAY_BLOCO = "Music Player Jukebox"
CHAVE_TEXTURA = "minha_jukebox_txt"
COMPONENT_ID = "meu_addon:jukebox_click"

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
    initEvent.blockComponentRegistry.registerCustomComponent('%COMPONENT_ID%', {
        onPlayerInteract: (e) => {
            const { block, player } = e;
            if (!player || player.isSneaking) return;

            const state = getState(block);
            const tracks = getActiveTracks(state.activePlaylist);
            const currentTrack = tracks[state.index];
            
            const form = new ActionFormData()
                .title("§2Music Player")
                .body(
                    `§fTocando agora:\n` +
                    `§a${state.playing && currentTrack ? "♫ " + currentTrack.name : "§7(Parado)"}\n\n` +
                    `§fPlaylist: §e${state.activePlaylist}\n` +
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
        form.button(`§f${t.name}\n§7${timeStr}`, icon);
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
"""

def verificar_ferramentas():
    if not os.path.exists(FFMPEG_EXE):
        print("ERRO: ffmpeg.exe não encontrado.")
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
                "minecraft:material_instances": { "*": { "texture": CHAVE_TEXTURA, "render_method": "opaque" } },
                "minecraft:custom_components": [ COMPONENT_ID ]
            }
        }
    }
    salvar_arquivo_seguro(os.path.join(PASTA_SOURCE, "BP", "blocks", "jukebox.json"), BLOCK_BP, is_json=True)
    
    # 2. Resource
    terrain_texture = {
        "resource_pack_name": "jukebox_rp",
        "texture_name": "atlas.terrain",
        "padding": 8,
        "num_mip_levels": 4,
        "texture_data": { CHAVE_TEXTURA: { "textures": "textures/blocks/jukebox_side" } }
    }
    salvar_arquivo_seguro(os.path.join(PASTA_SOURCE, "RP", "textures", "terrain_texture.json"), terrain_texture, is_json=True)
    
    criar_pasta_se_nao_existir(os.path.join(PASTA_SOURCE, "RP", "textures", "jukebox_icons"))

    # Manifests
    uuid_bp, uuid_rp = str(uuid.uuid4()), str(uuid.uuid4())
    
    bp_manifest = {
        "format_version": 2,
        "header": { "name": "Music Player BP", "description": "V5 Fixed Icons", "uuid": uuid_bp, "version": [1, 0, 0], "min_engine_version": [1, 21, 0] },
        "modules": [ { "type": "data", "uuid": str(uuid.uuid4()), "version": [1, 0, 0] }, { "type": "script", "language": "javascript", "uuid": str(uuid.uuid4()), "version": [1, 0, 0], "entry": "scripts/main.js" } ],
        "dependencies": [ { "module_name": "@minecraft/server", "version": "1.12.0" }, { "module_name": "@minecraft/server-ui", "version": "1.2.0" }, { "uuid": uuid_rp, "version": [1, 0, 0] } ]
    }
    rp_manifest = {
        "format_version": 2,
        "header": { "name": "Music Player RP", "description": "V5 Fixed Icons", "uuid": uuid_rp, "version": [1, 0, 0], "min_engine_version": [1, 21, 0] },
        "modules": [ { "type": "resources", "uuid": str(uuid.uuid4()), "version": [1, 0, 0] } ]
    }

    salvar_arquivo_seguro(os.path.join(PASTA_SOURCE, "BP", "manifest.json"), bp_manifest, is_json=True)
    salvar_arquivo_seguro(os.path.join(PASTA_SOURCE, "RP", "manifest.json"), rp_manifest, is_json=True)

def gerar_recipe():
    caminho_recipe = os.path.join(PASTA_SOURCE, "BP", "recipes", "jukebox_recipe.json")
    recipe_json = {
        "format_version": "1.21.0",
        "minecraft:recipe_shaped": {
            "description": { "identifier": f"{MEU_BLOCO_ID}_recipe" },
            "tags": [ "crafting_table" ],
            "pattern": [
                "PPP",
                "PDP",
                "PPP"
            ],
            "key": {
                "P": { "item": "minecraft:planks" },
                "D": { "item": "minecraft:gold_nugget" }
            },
            "result": { "item": MEU_BLOCO_ID }
        }
    }
    salvar_arquivo_seguro(caminho_recipe, recipe_json, is_json=True)

def main():
    print("--- GERANDO MUSIC PLAYER V5 (ÍCONES FIXOS) ---")
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

    if not os.path.exists(PASTA_MUSICA): os.makedirs(PASTA_MUSICA, exist_ok=True)
    print("Processando faixas e playlists...")

    for root, dirs, files in os.walk(PASTA_MUSICA):
        nome_pasta = os.path.basename(root)
        if nome_pasta == os.path.basename(PASTA_MUSICA):
            playlist_name = "Geral"
            playlist_slug = "geral"
        else:
            playlist_name = nome_pasta.replace("_", " ").title()
            playlist_slug = nome_pasta.lower().replace(" ", "_")

        arquivos_audio = [f for f in files if f.lower().endswith(('.mp3','.wav','.ogg','.m4a','.flac'))]
        for f in arquivos_audio:
            base_name = os.path.splitext(f)[0]
            name_clean_base = "".join([c for c in base_name.lower().replace(" ", "_") if c.isalnum() or c == "_"])
            name_clean = f"{playlist_slug}_{name_clean_base}" if playlist_slug != "geral" else name_clean_base

            src = os.path.join(root, f)
            dst = os.path.join(PASTA_CACHE_AUDIO, f"{name_clean}.ogg")
            subprocess.run([FFMPEG_EXE, '-y', '-i', src, '-vn', '-ac', '1', '-acodec', 'libvorbis', dst], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

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

    path_js = os.path.join(PASTA_SOURCE, "BP", "scripts", "main.js")
    js_content = JS_TEMPLATE.replace("%PLAYLIST_JSON%", json.dumps(playlist_data, indent=4))\
                            .replace("%BLOCK_ID%", MEU_BLOCO_ID)\
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