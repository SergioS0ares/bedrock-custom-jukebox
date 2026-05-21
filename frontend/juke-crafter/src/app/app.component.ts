import { Component } from '@angular/core';
import { HttpClient, HttpClientModule } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { MatRippleModule } from '@angular/material/core';
import { MatSnackBar, MatSnackBarModule } from '@angular/material/snack-bar';
import { MatTooltipModule } from '@angular/material/tooltip';

interface TrackMeta {
  filename: string;
  playlist: string;
  icon_filename?: string;
}

@Component({
  selector: 'app-root',
  templateUrl: './app.component.html',
  styleUrls: ['./app.component.scss'],
  standalone: true,
  imports: [CommonModule, FormsModule, HttpClientModule,
    MatRippleModule, MatSnackBarModule, MatTooltipModule]
})
export class AppComponent {
  constructor(private http: HttpClient, private snack: MatSnackBar) {
    if (typeof window !== 'undefined') this.loadTracks();
  }

  nomeAddon = 'Meu_Pacote_De_Musicas';
  arquivosSelecionados: File[] = [];
  playlists: string[] = ['Geral'];
  metadados: TrackMeta[] = [];

  // tracks CRUD (local cache)
  tracks: Array<{ id: string; type: 'file' | 'youtube'; filename?: string; file?: File | null; url?: string; playlist: string }> = [];

  isCarregando = false;
  youtubeLinksText = '';
  linkPlaylist = 'Geral';
  currentLang: 'pt' | 'en' = 'en';
  navOpen = false;

  // Image URLs — drop your custom PNGs into src/assets/icons/ to override.
  // If the file is missing, the inline SVG fallback in the template is used.
  imageUrls = {
    logo:    '/assets/icons/logo-cube.png',
    disc:    '/assets/icons/disc-vinyl.png',
    folder:  '/assets/icons/folder-yellow.png',
    youtube: '/assets/icons/youtube-icon.png'
  };

  // Toggle to true once you have placed the custom images in /assets/icons/
  useCustomImages = false;

  // Translations
  labels: any = {
    pt: {
      title: 'Criador de Addon de Jukebox Bedrock',
      navHome: 'Início',
      navMyAddons: 'Meus Addons',
      navCommunity: 'Comunidade',
      navSupport: 'Suporte',
      aboutTitle: 'Sobre e Primeiros Passos',
      howToUse: 'Como Usar',
      howToInstall: 'Como Instalar',
      installLine1: 'Basta baixar o arquivo .mcaddon gerado e dar duplo clique.',
      installLine2: 'O Minecraft Bedrock Edition vai importar automaticamente seu pacote de jukebox personalizado! É só clicar no arquivo.',
      createPlaylists: 'Criar Playlists',
      uploadMp3s: 'Enviar MP3s',
      browseFiles: 'Procurar Arquivos',
      pasteYoutube: 'Colar Links do YouTube',
      addPlaylist: 'Adicionar Playlist',
      addSong: 'Adicionar Música',
      generateAddon: 'GERAR MOD (.mcaddon)',
      generating: 'Gerando...',
      uploadNote: 'Formato suportado: .mp3 (até 50MB por arquivo)',
      playlistForLinks: 'Playlist para os links',
      playlists: 'Playlists',
      tracks: 'Faixas',
      dragHere: 'Arraste as faixas aqui',
      nameAddon: 'Nome do Addon',
      playlistName: 'Nome da Playlist',
      youtubeUrl: 'Cole a URL do vídeo do YouTube...',
      youtubeNote: '*Links do YouTube são processados automaticamente.*',
      uploadOrPaste: 'Envie MP3s ou cole links do YouTube',
      nameTracks: 'Nomeie suas faixas',
      clickGenerate: 'Clique em "Gerar Mod"',
      footer: '© Criador de Addon de Jukebox 2024',
      noTracksAlert: 'Adicione pelo menos uma faixa ou link.',
      generateError: 'Falha ao gerar o addon. Confira o console.',
      generateSuccess: 'Addon gerado com sucesso!'
    },
    en: {
      title: 'Bedrock Jukebox Addon Maker',
      navHome: 'Home',
      navMyAddons: 'My Addons',
      navCommunity: 'Community',
      navSupport: 'Support',
      aboutTitle: 'About & Getting Started',
      howToUse: 'How to Use',
      howToInstall: 'How to Install',
      installLine1: 'Simply download your generated .mcaddon file and double-click it.',
      installLine2: 'Minecraft Bedrock Edition will automatically import your custom jukebox pack! Just click the file.',
      createPlaylists: 'Create Playlists',
      uploadMp3s: 'Upload MP3s',
      browseFiles: 'Browse Files',
      pasteYoutube: 'Paste YouTube Links',
      addPlaylist: 'Add Playlist',
      addSong: 'Add Song',
      generateAddon: 'GENERATE MOD (.mcaddon)',
      generating: 'Generating...',
      uploadNote: 'Supported format: .mp3 (Max 50MB per file)',
      playlistForLinks: 'Playlist for links',
      playlists: 'Playlists',
      tracks: 'Tracks',
      dragHere: 'Drag tracks here',
      nameAddon: 'Addon Name',
      playlistName: 'Playlist Name',
      youtubeUrl: 'Paste YouTube Video URL...',
      youtubeNote: '*YouTube links are automatically processed.*',
      uploadOrPaste: 'Upload MP3s or paste YouTube links',
      nameTracks: 'Name your tracks',
      clickGenerate: 'Click "Generate Mod"',
      footer: '© Jukebox Addon Maker 2024',
      noTracksAlert: 'Add at least one track or link.',
      generateError: 'Failed to generate addon. Check the console.',
      generateSuccess: 'Addon generated successfully!'
    }
  };

  

  onFileSelected(event: any) {
    const files: FileList = event.target.files;
    if (files.length > 0) {
      const arr = Array.from(files);
      for (const f of arr) {
        const id = cryptoRandomId();
        this.tracks.push({ id, type: 'file', filename: f.name, file: f, playlist: 'Geral' });
      }
      this.saveTracks();
    }
  }

  addYoutubeLink() {
    const url = this.youtubeLinksText && this.youtubeLinksText.trim();
    if (!url) return;
    const id = cryptoRandomId();
    this.tracks.push({ id, type: 'youtube', url, playlist: this.linkPlaylist });
    this.youtubeLinksText = '';
    this.saveTracks();
  }

  removeTrack(id: string) {
    this.tracks = this.tracks.filter(t => t.id !== id);
    this.saveTracks();
  }

  setPlaylistForTrack(id: string, playlist: string) {
    const t = this.tracks.find(x => x.id === id);
    if (t) { t.playlist = playlist; this.saveTracks(); }
  }

  saveTracks() {
    try {
      if (typeof window !== 'undefined' && (window as any).localStorage) {
        localStorage.setItem('juke_tracks_v1', JSON.stringify(this.tracks.map(t => ({ id: t.id, type: t.type, filename: t.filename, url: t.url, playlist: t.playlist }))));
      }
    } catch (e) { console.warn('Failed to save tracks', e); }
  }

  loadTracks() {
    try {
      if (typeof window !== 'undefined' && (window as any).localStorage) {
        const raw = localStorage.getItem('juke_tracks_v1');
        if (raw) {
          const parsed = JSON.parse(raw);
          this.tracks = parsed.map((p: any) => ({ id: p.id, type: p.type, filename: p.filename, file: null, url: p.url, playlist: p.playlist }));
        }
      }
    } catch (e) { console.warn('Failed to load tracks', e); }
  }

  addPlaylist(name?: string) {
    const raw = (name ?? prompt('Playlist name:') ?? '').trim();
    if (!raw) return;
    if (!this.playlists.includes(raw)) this.playlists.push(raw);
  }

  removePlaylist(name: string) {
    if (name === 'Geral') return;
    this.playlists = this.playlists.filter(p => p !== name);
    // Reatribui tracks dessa playlist para Geral
    this.tracks.forEach(t => { if (t.playlist === name) t.playlist = 'Geral'; });
    this.saveTracks();
  }

  private toast(msg: string, action = 'OK', ms = 3500) {
    this.snack.open(msg, action, { duration: ms, panelClass: ['mc-snack'] });
  }

  gerarAddon() {
    if (this.tracks.length === 0) { this.toast(this.t('noTracksAlert')); return; }

    this.isCarregando = true;
    const formData = new FormData();
    formData.append('nome_addon', this.nomeAddon);

    const metadados: any[] = [];
    const youtubeLinks: string[] = [];

    for (const t of this.tracks) {
      if (t.type === 'file' && t.file) {
        formData.append('arquivos', t.file, t.filename || t.file.name);
        metadados.push({ filename: t.filename || t.file.name, playlist: t.playlist });
      } else if (t.type === 'youtube' && t.url) {
        youtubeLinks.push(t.url);
      }
    }

    formData.append('metadados_json', JSON.stringify(metadados));
    if (youtubeLinks.length > 0) formData.append('youtube_links', youtubeLinks.join('\n'));
    if (youtubeLinks.length > 0) formData.append('link_playlist', this.linkPlaylist);

    this.http.post('http://localhost:8000/api/build-addon', formData, { responseType: 'blob' }).subscribe({
      next: (blob: Blob) => {
        const url = window.URL.createObjectURL(blob);
        const link = document.createElement('a');
        link.href = url;
        link.download = `${this.nomeAddon}.mcaddon`;
        link.click();
        window.URL.revokeObjectURL(url);
        this.isCarregando = false;
        this.toast(this.t('generateSuccess'));
      },
      error: (err) => {
        console.error('Erro ao gerar o Addon:', err);
        this.toast(this.t('generateError'));
        this.isCarregando = false;
      }
    });
  }

  t(key: string) {
    return (this.labels[this.currentLang] && this.labels[this.currentLang][key]) || key;
  }

  toggleLanguage() {
    this.currentLang = this.currentLang === 'pt' ? 'en' : 'pt';
  }
}

function cryptoRandomId(len = 8) {
  return Math.random().toString(36).slice(2, 2 + len) + Date.now().toString(36).slice(-4);
}
