import { Component, inject } from '@angular/core';
import { HttpClient } from '@angular/common/http';
import { CommonModule } from '@angular/common';
import { FormsModule } from '@angular/forms';
import { HttpClientModule } from '@angular/common/http';
import { MatToolbarModule } from '@angular/material/toolbar';
import { MatCardModule } from '@angular/material/card';
import { MatFormFieldModule } from '@angular/material/form-field';
import { MatInputModule } from '@angular/material/input';
import { MatButtonModule } from '@angular/material/button';
import { MatSelectModule } from '@angular/material/select';
import { MatListModule } from '@angular/material/list';
import { MatIconModule } from '@angular/material/icon';
import { MatChipsModule } from '@angular/material/chips';

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
    MatToolbarModule, MatCardModule, MatFormFieldModule, MatInputModule,
    MatButtonModule, MatSelectModule, MatListModule, MatIconModule, MatChipsModule]
})
export class AppComponent {
  private http = inject(HttpClient);

  nomeAddon = 'Meu_Pacote_De_Musicas';
  arquivosSelecionados: File[] = [];
  playlists: string[] = ['Geral'];
  metadados: TrackMeta[] = [];

  // tracks CRUD (local cache)
  tracks: Array<{ id: string; type: 'file' | 'youtube'; filename?: string; file?: File | null; url?: string; playlist: string }> = [];

  isCarregando = false;
  youtubeLinksText = '';
  linkPlaylist = 'Geral';
  currentLang: 'pt' | 'en' = 'pt';

  // Default image URLs (can be replaced by any online pixel-art icons)
  imageUrls = {
    disc: '/assets/icons/disc.svg',
    folder: '/assets/icons/folder.svg',
    youtube: '/assets/icons/youtube.svg',
    generateBadge: '/assets/icons/check.svg'
  };

  // Translations
  labels: any = {
    pt: {
      title: 'Bedrock Jukebox Addon Maker',
      howToUse: 'Como usar',
      createPlaylists: 'Criar Playlists',
      addPlaylist: 'Adicionar playlist',
      browseFiles: 'Procurar arquivos',
      pasteYoutube: 'Colar links do YouTube',
      addSong: 'Adicionar música',
      generateAddon: 'GERAR MOD (.mcaddon)',
      uploadNote: 'Formato suportado: .mp3/.ogg/.wav (até 50MB por arquivo)',
      playlistForLinks: 'Playlist para os links',
      playlists: 'Playlists',
      dragHere: 'Arraste as faixas aqui',
      nameAddon: 'Nome do Addon'
    },
    en: {
      title: 'Bedrock Jukebox Addon Maker',
      howToUse: 'How to Use',
      createPlaylists: 'Create Playlists',
      addPlaylist: 'Add Playlist',
      browseFiles: 'Browse Files',
      pasteYoutube: 'Paste YouTube Links',
      addSong: 'Add Song',
      generateAddon: 'GENERATE MOD (.mcaddon)',
      uploadNote: 'Supported: .mp3/.ogg/.wav (up to 50MB/file)',
      playlistForLinks: 'Playlist for links',
      playlists: 'Playlists',
      dragHere: 'Drag tracks here',
      nameAddon: 'Addon Name'
    }
  };

  constructor() { if (typeof window !== 'undefined') this.loadTracks(); }

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

  addPlaylist() {
    const name = prompt('Nome da nova playlist:');
    if (!name) return;
    const slug = name.trim();
    if (slug && !this.playlists.includes(slug)) this.playlists.push(slug);
  }

  removePlaylist(name: string) {
    if (name === 'Geral') return;
    this.playlists = this.playlists.filter(p => p !== name);
    // Reatribui tracks dessa playlist para Geral
    this.tracks.forEach(t => { if (t.playlist === name) t.playlist = 'Geral'; });
    this.saveTracks();
  }

  gerarAddon() {
    if (this.tracks.length === 0) { alert('Adicione pelo menos uma faixa ou link.'); return; }

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
      },
      error: (err) => {
        console.error('Erro ao gerar o Addon:', err);
        alert('Falha ao processar as músicas. Veja o console.');
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
