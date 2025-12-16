
import { world, system } from "@minecraft/server";

// Lista de IDs de música gerada automaticamente pelo Python
const MUSIC_TRACKS = ["custom.music.0"];

world.beforeEvents.playerInteractWithBlock.subscribe((event) => {
    const { player, block } = event;
    
    // Verifica se o bloco clicado é a nossa Jukebox
    if (block.typeId === "meu_addon:custom_jukebox") {
        const randomTrack = MUSIC_TRACKS[Math.floor(Math.random() * MUSIC_TRACKS.length)];
        
        // Toca o som para todos (@a) na posição do jogador
        // O comando playsound usa coordenadas relativas (~)
        player.runCommandAsync(`playsound ${randomTrack} @a ~ ~ ~ 10 1`);
        
        player.sendMessage(`§a[Jukebox] Tocando: ${randomTrack}`);
        
        // Cancela a interação para não abrir inventários (se houver)
        event.cancel = true; 
    }
});
