import os
import json
import zipfile
import subprocess
import shutil
import uuid

# --- CONFIGURAÇÕES ---
BASE_DIR = os.path.abspath(os.getcwd())
NOME_ADDON = "Jukebox_Final_Perfect"

PASTA_SOURCE = os.path.join(BASE_DIR, "addon_source")
PASTA_MUSICA = os.path.join(BASE_DIR, "user_music")
FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")
PASTA_CACHE_AUDIO = os.path.join(BASE_DIR, "_audio_cache_")

# Estrutura
SUBPASTA_AUDIO = "sounds/jukebox" 
PASTA_DEFINICAO = "sounds"

# --- JAVASCRIPT: AGORA COM DETECTOR DE QUEBRA DE BLOCO ---
JS_TEMPLATE = """
import { world, system } from "@minecraft/server";
import { ActionFormData } from "@minecraft/server-ui";

const MUSIC_TRACKS = %MUSICAS_ARRAY%;
// SEU ID (Verifique se bate com o jukebox.json)
const BLOCK_ID = "meu_addon:custom_jukebox"; 

// 1. EVENTO DE CLIQUE (Tocar Música)
world.afterEvents.playerInteractWithBlock.subscribe((event) => {
    const { block, player } = event;

    if (block.typeId === BLOCK_ID) {
        
        const form = new ActionFormData()
            .title("Jukebox")
            .body("Selecione o disco:");

        for (const track of MUSIC_TRACKS) {
            const name = track.split(".").pop().replace(/_/g, " ");
            form.button("♫ " + name);
        }
        form.button("§c■ Parar Som");

        system.run(() => {
            form.show(player).then((response) => {
                if (response.canceled) return;
                
                const selection = response.selection;

                // Coordenadas formatadas
                const x = block.location.x.toFixed(2);
                const y = block.location.y.toFixed(2);
                const z = block.location.z.toFixed(2);

                // Para sons anteriores num raio de 64 blocos
                player.dimension.runCommandAsync(`stopsound @a[x=${x},y=${y},z=${z},r=64]`);

                if (selection === MUSIC_TRACKS.length) {
                    player.sendMessage("§cSom parado.");
                    return;
                }

                const track = MUSIC_TRACKS[selection];

                // --- AJUSTE DE VOLUME E DISTÂNCIA ---
                // Volume 4.0 no comando = Raio de aprox 64 blocos.
                // Se passar disso, o som corta abruptamente ou fica inaudível.
                const cmd = `playsound ${track} @a ${x} ${y} ${z} 4.0 1.0`;
                
                player.dimension.runCommandAsync(cmd);
                player.sendMessage(`§aTocando: ${track}`);

            }).catch(e => console.error(e));
        });
    }
});

// 2. EVENTO DE QUEBRA (Parar Música)
world.afterEvents.playerBreakBlock.subscribe((event) => {
    const { block, brokenBlockPermutation } = event;

    // Verifica se o bloco quebrado era a nossa Jukebox
    if (brokenBlockPermutation.type.id === BLOCK_ID) {
        
        const x = block.location.x.toFixed(2);
        const y = block.location.y.toFixed(2);
        const z = block.location.z.toFixed(2);

        // Manda parar qualquer som num raio pequeno (4 blocos) ao redor de onde o bloco estava
        // Usamos executeCommand para garantir que pare para todos
        block.dimension.runCommandAsync(`stopsound @a[x=${x},y=${y},z=${z},r=10]`);
        
        // Mensagem opcional (pode remover se quiser)
        // console.warn("Jukebox quebrada, som interrompido.");
    }
});
"""

def verificar_ffmpeg():
    if not os.path.exists(FFMPEG_EXE):
        print("ERRO: ffmpeg.exe não encontrado.")
        return False
    return True

def gerar_manifests_novos():
    uuid_bp = str(uuid.uuid4())
    uuid_rp = str(uuid.uuid4())
    uuid_script = str(uuid.uuid4())

    # Manifest BP
    bp_manifest = {
        "format_version": 2,
        "header": {
            "name": "Jukebox BP Final",
            "description": "Com Stop on Break",
            "uuid": uuid_bp,
            "version": [1, 0, 0],
            "min_engine_version": [1, 20, 80]
        },
        "modules": [
            { "type": "data", "uuid": str(uuid.uuid4()), "version": [1, 0, 0] },
            { "type": "script", "language": "javascript", "uuid": uuid_script, "version": [1, 0, 0], "entry": "scripts/main.js" }
        ],
        "dependencies": [
            { "module_name": "@minecraft/server", "version": "1.11.0" },
            { "module_name": "@minecraft/server-ui", "version": "1.2.0" },
            { "uuid": uuid_rp, "version": [1, 0, 0] }
        ]
    }

    # Manifest RP
    rp_manifest = {
        "format_version": 2,
        "header": {
            "name": "Jukebox RP Final",
            "description": "Sons Limitados a 64 Blocos",
            "uuid": uuid_rp,
            "version": [1, 0, 0],
            "min_engine_version": [1, 20, 80]
        },
        "modules": [
            { "type": "resources", "uuid": str(uuid.uuid4()), "version": [1, 0, 0] }
        ]
    }

    path_bp = os.path.join(PASTA_SOURCE, "BP")
    path_rp = os.path.join(PASTA_SOURCE, "RP")
    if not os.path.exists(path_bp): os.makedirs(path_bp)
    if not os.path.exists(path_rp): os.makedirs(path_rp)

    with open(os.path.join(path_bp, "manifest.json"), "w", encoding='utf-8') as f:
        json.dump(bp_manifest, f, indent=4)
    with open(os.path.join(path_rp, "manifest.json"), "w", encoding='utf-8') as f:
        json.dump(rp_manifest, f, indent=4)

def main():
    print("--- GERANDO VERSÃO PERFEITA ---")
    if not verificar_ffmpeg(): return
    if os.path.exists(PASTA_CACHE_AUDIO): shutil.rmtree(PASTA_CACHE_AUDIO)
    os.makedirs(PASTA_CACHE_AUDIO)

    gerar_manifests_novos()

    lista_ids = []
    sound_defs = { "format_version": "1.14.0", "sound_definitions": {} }

    if not os.path.exists(PASTA_MUSICA): os.makedirs(PASTA_MUSICA)
    files = [f for f in os.listdir(PASTA_MUSICA) if f.lower().endswith(('.mp3','.wav','.ogg','.m4a','.flac'))]

    print(f"Processando {len(files)} arquivos...")

    for f in files:
        name_clean = os.path.splitext(f)[0].lower().replace(" ", "_")
        name_clean = "".join([c for c in name_clean if c.isalnum() or c == "_"])
        
        src = os.path.join(PASTA_MUSICA, f)
        dst = os.path.join(PASTA_CACHE_AUDIO, f"{name_clean}.ogg")

        # MONO para 3D
        subprocess.run([FFMPEG_EXE, '-y', '-i', src, '-vn', '-ac', '1', '-acodec', 'libvorbis', dst], 
                       stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)

        sound_id = f"custom.jukebox.{name_clean}"
        lista_ids.append(sound_id)
        
        path_in_json = f"{SUBPASTA_AUDIO}/{name_clean}"
        
        # --- CONFIGURAÇÃO DE DISTÂNCIA FIXA ---
        # max_distance: 64.0 = Limite duro. Passou de 64 blocos, o som corta.
        sound_defs["sound_definitions"][sound_id] = {
            "category": "record", 
            "min_distance": 4.0,
            "max_distance": 64.0, 
            "sounds": [
                {
                    "name": path_in_json, 
                    "stream": True,
                    "load_on_low_memory": True
                }
            ]
        }
        print(f"Configurado: {sound_id}")

    path_sounds_root = os.path.join(PASTA_SOURCE, "RP", PASTA_DEFINICAO)
    if not os.path.exists(path_sounds_root): os.makedirs(path_sounds_root)
    
    with open(os.path.join(path_sounds_root, "sound_definitions.json"), "w", encoding='utf-8') as f:
        json.dump(sound_defs, f, indent=4)

    path_js = os.path.join(PASTA_SOURCE, "BP/scripts")
    if not os.path.exists(path_js): os.makedirs(path_js)
    with open(os.path.join(path_js, "main.js"), "w", encoding='utf-8') as f:
        f.write(JS_TEMPLATE.replace("%MUSICAS_ARRAY%", json.dumps(lista_ids)))

    out = os.path.join(BASE_DIR, f"{NOME_ADDON}.mcaddon")
    with zipfile.ZipFile(out, "w", zipfile.ZIP_DEFLATED) as z:
        for root, _, files in os.walk(PASTA_SOURCE):
            for file in files:
                abs_path = os.path.join(root, file)
                rel_path = os.path.relpath(abs_path, PASTA_SOURCE)
                z.write(abs_path, rel_path)
        
        for ogg in os.listdir(PASTA_CACHE_AUDIO):
            path_zip = f"RP/{SUBPASTA_AUDIO}/{ogg}"
            z.write(os.path.join(PASTA_CACHE_AUDIO, ogg), path_zip)

    print(f"--- SUCESSO! ---")
    print(f"Arquivo gerado: {out}")
    print("Teste: O som deve sumir após ~64 blocos e PARAR IMEDIATAMENTE ao quebrar o bloco.")

if __name__ == "__main__":
    main()