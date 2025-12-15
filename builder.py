import os
import json
import shutil
import zipfile
import subprocess

# --- Configurações ---
BASE_DIR = os.path.abspath(os.getcwd())
NOME_ADDON = "JukeboxPro"

# Pastas
PASTA_SOURCE = os.path.join(BASE_DIR, "addon_source")
PASTA_MUSICA = os.path.join(BASE_DIR, "user_music")
FFMPEG_EXE = os.path.join(BASE_DIR, "ffmpeg.exe")
PASTA_CACHE_AUDIO = os.path.join(BASE_DIR, "_audio_cache_")

# Template JS
JS_TEMPLATE = """
import { world, system } from "@minecraft/server";
const MUSIC_TRACKS = %MUSICAS_ARRAY%;
world.beforeEvents.itemUseOn.subscribe((event) => {
    const { source, itemStack, block } = event;
    // IMPORTANTE: Verifique se o ID do bloco no jogo é igual a este abaixo:
    if (block.typeId === "meu_addon:custom_jukebox") {
        const randomTrack = MUSIC_TRACKS[Math.floor(Math.random() * MUSIC_TRACKS.length)];
        source.runCommandAsync(`playsound ${randomTrack} @a[r=20] ${block.location.x} ${block.location.y} ${block.location.z}`);
        source.sendMessage(`§aTocando: ${randomTrack}`);
    }
});
"""

def main():
    print(f"--- Iniciando Build (Correção Final) ---")

    if not os.path.exists(FFMPEG_EXE):
        print("❌ FFMPEG não encontrado."); return
    if not os.path.exists(PASTA_SOURCE):
        print("❌ Pasta addon_source não encontrada."); return

    # 1. Preparar Cache de Áudio
    if os.path.exists(PASTA_CACHE_AUDIO):
        shutil.rmtree(PASTA_CACHE_AUDIO, ignore_errors=True)
    os.makedirs(PASTA_CACHE_AUDIO, exist_ok=True)

    # 2. Processar Músicas
    if not os.path.exists(PASTA_MUSICA):
        os.makedirs(PASTA_MUSICA)
    
    arquivos_musica = os.listdir(PASTA_MUSICA)
    musicas_ids = []
    sound_defs = {"format_version": "1.14.0", "sound_definitions": {}}
    
    print(f"--- Convertendo {len(arquivos_musica)} músicas ---")
    
    contador = 0
    for arquivo in arquivos_musica:
        caminho_origem = os.path.join(PASTA_MUSICA, arquivo)
        nome_base = os.path.splitext(arquivo)[0]
        caminho_convertido = os.path.join(PASTA_CACHE_AUDIO, f"{nome_base}.ogg")
        
        # CORREÇÃO 1: Mudado '-log_level' para '-loglevel'
        comando = [FFMPEG_EXE, "-y", "-i", caminho_origem, "-vn", "-c:a", "libvorbis", "-loglevel", "error", caminho_convertido]
        
        valido = False
        if arquivo.lower().endswith((".mp3", ".wav")):
            print(f"Convertendo: {arquivo}")
            result = subprocess.run(comando)
            if result.returncode == 0:
                valido = True
            else:
                print(f"❌ Erro ao converter {arquivo}")
        elif arquivo.lower().endswith(".ogg"):
            shutil.copy2(caminho_origem, caminho_convertido)
            valido = True
            
        if valido:
            id_som = f"custom.music.{contador}"
            sound_defs["sound_definitions"][id_som] = {"category": "record", "sounds": [f"sounds/music/{nome_base}"]}
            musicas_ids.append(id_som)
            contador += 1

    # 3. Criar o Arquivo .mcaddon
    output_filename = os.path.join(BASE_DIR, f"{NOME_ADDON}.mcaddon")
    print(f"--- Gerando arquivo: {NOME_ADDON}.mcaddon ---")
    
    with zipfile.ZipFile(output_filename, 'w', zipfile.ZIP_DEFLATED) as zipf:
        
        # A) Adicionar arquivos originais (COM FILTRO PARA NÃO DUPLICAR)
        for root, dirs, files in os.walk(PASTA_SOURCE):
            for file in files:
                # CORREÇÃO 2: Pula arquivos que vamos gerar automaticamente
                if file == "main.js" or file == "sound_definitions.json":
                    continue
                
                caminho_real = os.path.join(root, file)
                caminho_no_zip = os.path.relpath(caminho_real, PASTA_SOURCE)
                zipf.write(caminho_real, caminho_no_zip)

        # B) Injetar as músicas convertidas
        for arquivo_ogg in os.listdir(PASTA_CACHE_AUDIO):
            caminho_real = os.path.join(PASTA_CACHE_AUDIO, arquivo_ogg)
            zipf.write(caminho_real, f"RP/sounds/music/{arquivo_ogg}")

        # C) Injetar os arquivos gerados
        zipf.writestr("RP/sound_definitions.json", json.dumps(sound_defs, indent=4))
        
        js_final = JS_TEMPLATE.replace("%MUSICAS_ARRAY%", json.dumps(musicas_ids))
        zipf.writestr("BP/scripts/main.js", js_final)

    # Limpeza
    try:
        shutil.rmtree(PASTA_CACHE_AUDIO)
    except:
        pass

    print(f"✅ SUCESSO TOTAL! Agora sim. Arquivo: {output_filename}")

if __name__ == "__main__":
    main()