
import { world, system } from "@minecraft/server";
const MUSIC_TRACKS = ["custom.music.0"];
world.beforeEvents.itemUseOn.subscribe((event) => {
    const { source, itemStack, block } = event;
    // IMPORTANTE: Verifique se o ID do bloco no jogo é igual a este abaixo:
    if (block.typeId === "meu_addon:custom_jukebox") {
        const randomTrack = MUSIC_TRACKS[Math.floor(Math.random() * MUSIC_TRACKS.length)];
        source.runCommandAsync(`playsound ${randomTrack} @a[r=20] ${block.location.x} ${block.location.y} ${block.location.z}`);
        source.sendMessage(`§aTocando: ${randomTrack}`);
    }
});
