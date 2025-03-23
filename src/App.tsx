import React, { useState, useRef, useEffect } from 'react';
import { Search, Music2, Download, Play, Pause, Volume2, VolumeX, SkipBack, SkipForward, Loader2, AudioWaveform as Waveform, RotateCcw } from 'lucide-react';
import WaveSurfer from 'wavesurfer.js';

interface Track {
  videoId: string;
  title: string;
  artist: string;
  thumbnail: string;
}

interface EqualizerBand {
  frequency: number;
  gain: number;
}

const DEFAULT_EQUALIZER_BANDS: EqualizerBand[] = [
  { frequency: 32, gain: 0 },
  { frequency: 64, gain: 0 },
  { frequency: 125, gain: 0 },
  { frequency: 250, gain: 0 },
  { frequency: 500, gain: 0 },
  { frequency: 1000, gain: 0 },
  { frequency: 2000, gain: 0 },
  { frequency: 4000, gain: 0 },
  { frequency: 8000, gain: 0 },
  { frequency: 16000, gain: 0 },
];

function App() {
  const [searchQuery, setSearchQuery] = useState('');
  const [tracks, setTracks] = useState<Track[]>([]);
  const [currentTrack, setCurrentTrack] = useState<Track | null>(null);
  const [isLoading, setIsLoading] = useState(false);
  const [audioUrl, setAudioUrl] = useState<string>('');
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);
  const [volume, setVolume] = useState(1);
  const [isMuted, setIsMuted] = useState(false);
  const [showEqualizer, setShowEqualizer] = useState(false);
  const [equalizerBands, setEqualizerBands] = useState<EqualizerBand[]>(DEFAULT_EQUALIZER_BANDS);
  
  const audioRef = useRef<HTMLAudioElement>(null);
  const audioContextRef = useRef<AudioContext | null>(null);
  const sourceNodeRef = useRef<MediaElementAudioSourceNode | null>(null);
  const equalizerNodesRef = useRef<BiquadFilterNode[]>([]);
  const waveformRef = useRef<WaveSurfer | null>(null);
  const waveformContainerRef = useRef<HTMLDivElement>(null);
  const playerRef = useRef<HTMLDivElement>(null);
  const isAudioInitialized = useRef<boolean>(false);
  const volumeControlRef = useRef<HTMLDivElement>(null);

  // Prevent scroll when adjusting equalizer sliders
  useEffect(() => {
    const preventScroll = (e: TouchEvent) => {
      if (showEqualizer) {
        e.preventDefault();
      }
    };

    document.addEventListener('touchmove', preventScroll, { passive: false });
    return () => {
      document.removeEventListener('touchmove', preventScroll);
    };
  }, [showEqualizer]);


  useEffect(() => {
    if (waveformContainerRef.current && audioRef.current) {
      waveformRef.current = WaveSurfer.create({
        container: waveformContainerRef.current,
        waveColor: '#8b5cf6',
        progressColor: '#6d28d9',
        cursorColor: '#4c1d95',
        barWidth: 2,
        barGap: 1,
        height: 40,
        normalize: true,
        mediaControls: true,
      });

      return () => {
        if (waveformRef.current) {
          waveformRef.current.destroy();
        }
      };
    }
  }, []);

  const initializeAudioContext = () => {
    if (!audioContextRef.current && audioRef.current && !isAudioInitialized.current) {
      audioContextRef.current = new AudioContext();
      sourceNodeRef.current = audioContextRef.current.createMediaElementSource(audioRef.current);

      equalizerNodesRef.current = equalizerBands.map(band => {
        const filter = audioContextRef.current!.createBiquadFilter();
        filter.type = band.frequency <= 32 ? 'lowshelf' : band.frequency >= 16000 ? 'highshelf' : 'peaking';
        filter.frequency.value = band.frequency;
        filter.gain.value = band.gain;
        filter.Q.value = 1;
        return filter;
      });

      sourceNodeRef.current.connect(equalizerNodesRef.current[0]);
      equalizerNodesRef.current.forEach((node, i) => {
        if (i < equalizerNodesRef.current.length - 1) {
          node.connect(equalizerNodesRef.current[i + 1]);
        }
      });
      equalizerNodesRef.current[equalizerNodesRef.current.length - 1].connect(audioContextRef.current.destination);
      
      isAudioInitialized.current = true;
    }
  };

const resetEqualizer = () => {
  // Обновляем состояние equalizerBands до значений по умолчанию
  setEqualizerBands([...DEFAULT_EQUALIZER_BANDS]);

  // Обновляем значения фильтров
  equalizerNodesRef.current.forEach((node, index) => {
    if (node) {
      node.gain.setValueAtTime(DEFAULT_EQUALIZER_BANDS[index].gain, audioContextRef.current?.currentTime || 0);
    }
  });
};

  const handleSearch = async () => {
    if (!searchQuery.trim()) return;
    
    setIsLoading(true);
    try {
      const response = await fetch(`/api/search?query=${encodeURIComponent(searchQuery)}`);
      if (!response.ok) throw new Error('Search failed');
      const data = await response.json();
      setTracks(data);
    } catch (error) {
      console.error('Search error:', error);
    } finally {
      setIsLoading(false);
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter') {
      handleSearch();
    }
  };

  const playTrack = async (track: Track) => {
    setCurrentTrack(track);
    const audioUrl = `/api/get_audio/${track.videoId}`;
    setAudioUrl(audioUrl);
    setIsPlaying(true);

    initializeAudioContext();

    if (waveformRef.current) {
      waveformRef.current.load(audioUrl);
      waveformRef.current.on('ready', () => {
        waveformRef.current?.play();
      });
    }

    if (audioContextRef.current?.state === 'suspended') {
      await audioContextRef.current.resume();
    }
  };

  const downloadTrack = (track: Track) => {
    window.location.href = `/api/get_audio/${track.videoId}`;
  };

  const togglePlay = async () => {
    if (audioRef.current) {
      initializeAudioContext();

      if (audioContextRef.current?.state === 'suspended') {
        await audioContextRef.current.resume();
      }

      if (isPlaying) {
        audioRef.current.pause();
        waveformRef.current?.pause();
      } else {
        audioRef.current.play();
        waveformRef.current?.play();
      }
      setIsPlaying(!isPlaying);
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
      setDuration(audioRef.current.duration);
    }
  };

  const handleSeek = (e: React.ChangeEvent<HTMLInputElement>) => {
    const time = parseFloat(e.target.value);
    if (audioRef.current) {
      audioRef.current.currentTime = time;
      setCurrentTime(time);
      if (waveformRef.current) {
        waveformRef.current.seekTo(time / duration);
      }
    }
  };

  const handleVolumeChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    e.stopPropagation();
    const value = parseFloat(e.target.value);
    setVolume(value);
    if (audioRef.current) {
      audioRef.current.volume = value;
    }
    if (value === 0) {
      setIsMuted(true);
    } else {
      setIsMuted(false);
    }
  };

  const handleEqualizerChange = (index: number, value: number) => {
    if (!audioContextRef.current || !isAudioInitialized.current) {
      return;
    }

    const newBands = [...equalizerBands];
    newBands[index].gain = value;
    setEqualizerBands(newBands);

    if (equalizerNodesRef.current[index]) {
      equalizerNodesRef.current[index].gain.setValueAtTime(value, audioContextRef.current.currentTime);
    }
  };

  const toggleMute = () => {
    if (audioRef.current) {
      if (isMuted) {
        audioRef.current.volume = volume;
        setIsMuted(false);
      } else {
        audioRef.current.volume = 0;
        setIsMuted(true);
      }
    }
  };

  const formatTime = (time: number) => {
    const minutes = Math.floor(time / 60);
    const seconds = Math.floor(time % 60);
    return `${minutes}:${seconds.toString().padStart(2, '0')}`;
  };

  const formatFrequency = (freq: number) => {
    return freq >= 1000 ? `${freq/1000}kHz` : `${freq}Hz`;
  };

  useEffect(() => {
    if (audioRef.current) {
      audioRef.current.volume = volume;
    }
  }, [volume]);

  return (
    <div className="min-h-screen bg-gradient-to-br from-gray-900 via-purple-900 to-gray-900 text-white">
      {/* Header */}
      <header className="px-4 sm:px-6 py-6 sm:py-8 bg-black/20">
        <div className="max-w-6xl mx-auto">
          <div className="flex items-center gap-3 mb-6 sm:mb-8">
            <Music2 className="w-6 h-6 sm:w-8 sm:h-8 text-purple-400" />
            <h1 className="text-2xl sm:text-3xl font-bold bg-clip-text text-transparent bg-gradient-to-r from-purple-400 to-pink-400">
              @FellGoodMusicBot
            </h1>
          </div>
          
          {/* Search Bar */}
          <div className="relative max-w-2xl">
            <input
              type="text"
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              onKeyPress={handleKeyPress}
              placeholder="Поиск треков..."
              className="w-full px-4 sm:px-6 py-3 sm:py-4 bg-white/5 backdrop-blur-lg rounded-xl pl-10 sm:pl-12 pr-4 focus:outline-none focus:ring-2 focus:ring-purple-400 transition-all border border-white/10"
            />
            <Search className="absolute left-3 sm:left-4 top-1/2 -translate-y-1/2 text-gray-400 w-4 h-4 sm:w-5 sm:h-5" />
            <button
              onClick={handleSearch}
              disabled={isLoading}
              className="absolute right-2 sm:right-4 top-1/2 -translate-y-1/2 bg-purple-500 hover:bg-purple-600 px-3 sm:px-4 py-1.5 sm:py-2 rounded-lg transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2 text-sm sm:text-base"
            >
              {isLoading ? (
                <>
                  <Loader2 className="w-4 h-4 animate-spin" />
                  Поиск...
                </>
              ) : (
                'Поиск'
              )}
            </button>
          </div>
        </div>
      </header>

      {/* Main Content */}
      <main className="px-4 sm:px-6 py-6 sm:py-8 pb-32">
        <div className="max-w-6xl mx-auto">
          {/* Tracks Grid */}
          <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4 sm:gap-6">
            {tracks.map((track) => (
              <div
                key={track.videoId}
                className="bg-white/5 backdrop-blur-lg rounded-xl p-4 hover:bg-white/10 transition-all group border border-white/10"
              >
                <div className="relative aspect-square mb-4 overflow-hidden rounded-lg">
                  <img
                    src={track.thumbnail}
                    alt={track.title}
                    className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-300"
                  />
                  <button
                    onClick={() => playTrack(track)}
                    className="absolute inset-0 flex items-center justify-center bg-black/40 opacity-0 group-hover:opacity-100 transition-opacity"
                  >
                    <Play className="w-12 h-12 text-white" />
                  </button>
                </div>
                <div className="space-y-2">
                  <h3 className="font-semibold text-base sm:text-lg truncate">{track.title}</h3>
                  <p className="text-gray-400 text-sm sm:text-base truncate">{track.artist}</p>
                  <div className="flex justify-between items-center pt-2">
                    <button
                      onClick={() => playTrack(track)}
                      className="text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-2 text-sm sm:text-base"
                    >
                      <Play className="w-4 h-4 sm:w-5 sm:h-5" />
                      Слушать
                    </button>
                    <button 
                      onClick={() => downloadTrack(track)}
                      className="text-purple-400 hover:text-purple-300 transition-colors flex items-center gap-2 text-sm sm:text-base"
                    >
                      <Download className="w-4 h-4 sm:w-5 sm:h-5" />
                      Скачать
                    </button>
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>
      </main>

      {/* Fixed Player */}
      {currentTrack && (
        <div className="fixed bottom-0 left-0 right-0 bg-black/95 backdrop-blur-xl border-t border-white/10 touch-none">
          <div className="max-w-6xl mx-auto p-4">
            <div className="flex flex-col gap-4">
              {/* Player Controls */}
              <div className="flex flex-col sm:flex-row items-start sm:items-center gap-4">
                {/* Track Info */}
                <div className="flex items-center gap-4 w-full sm:w-auto">
                  <img
                    src={currentTrack.thumbnail}
                    alt={currentTrack.title}
                    className="w-12 h-12 sm:w-16 sm:h-16 rounded-lg object-cover shadow-lg"
                  />
                  <div className="flex-1 min-w-0">
                    <h3 className="font-semibold text-sm sm:text-base truncate">{currentTrack.title}</h3>
                    <p className="text-gray-400 text-xs sm:text-sm truncate">{currentTrack.artist}</p>
                  </div>
                </div>
                
                {/* Playback Controls */}
                <div className="flex-1 w-full">
                  <div className="flex items-center justify-center gap-4 mb-2">
                    <button className="text-gray-400 hover:text-white transition-colors">
                      <SkipBack className="w-4 h-4 sm:w-5 sm:h-5" />
                    </button>
                    <button
                      onClick={togglePlay}
                      className="w-8 h-8 sm:w-10 sm:h-10 rounded-full bg-purple-500 hover:bg-purple-600 transition-colors flex items-center justify-center"
                    >
                      {isPlaying ? (
                        <Pause className="w-4 h-4 sm:w-5 sm:h-5" />
                      ) : (
                        <Play className="w-4 h-4 sm:w-5 sm:h-5" />
                      )}
                    </button>
                    <button className="text-gray-400 hover:text-white transition-colors">
                      <SkipForward className="w-4 h-4 sm:w-5 sm:h-5" />
                    </button>
                  </div>
                  
                  <div ref={waveformContainerRef} className="mb-2" />
                  
                  <div className="flex items-center gap-2 sm:gap-3">
                    <span className="text-xs sm:text-sm text-gray-400 w-8 sm:w-12 text-right">
                      {formatTime(currentTime)}
                    </span>
                    <input
                      type="range"
                      min="0"
                      max={duration || 0}
                      value={currentTime}
                      onChange={handleSeek}
                      className="flex-1 h-1 bg-gray-600 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500"
                    />
                    <span className="text-xs sm:text-sm text-gray-400 w-8 sm:w-12">
                      {formatTime(duration)}
                    </span>
                  </div>
                </div>
                
                {/* Volume Control */}
                <div ref={volumeControlRef} className="flex items-center gap-2 w-full sm:w-32 touch-none">
                  <button onClick={toggleMute} className="text-gray-400 hover:text-white transition-colors">
                    {isMuted ? (
                      <VolumeX className="w-4 h-4 sm:w-5 sm:h-5" />
                    ) : (
                      <Volume2 className="w-4 h-4 sm:w-5 sm:h-5" />
                    )}
                  </button>
                  <input
                    type="range"
                    min="0"
                    max="1"
                    step="0.01"
                    value={isMuted ? 0 : volume}
                    onChange={handleVolumeChange}
                    className="flex-1 h-1 bg-gray-600 rounded-lg appearance-none cursor-pointer [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-3 [&::-webkit-slider-thumb]:h-3 [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500"
                  />
                </div>
              </div>

              {/* Equalizer Controls */}
              <div className="flex items-center gap-4">
                <button
                  onClick={() => setShowEqualizer(!showEqualizer)}
                  className="flex items-center gap-2 text-sm text-purple-400 hover:text-purple-300 transition-colors"
                >
                  <Waveform className="w-4 h-4 sm:w-5 sm:h-5" />
                  {showEqualizer ? 'Скрыть эквалайзер' : 'Показать эквалайзер'}
                </button>
                {showEqualizer && (
                  <button
                    onClick={resetEqualizer}
                    className="flex items-center gap-2 text-sm text-purple-400 hover:text-purple-300 transition-colors"
                  >
                    <RotateCcw className="w-4 h-4" />
                    Сбросить
                  </button>
                )}
              </div>

              {/* Equalizer */}
              {showEqualizer && (
                <div className="pt-4 border-t border-white/10">
                  <div className="grid grid-cols-5 sm:grid-cols-10 gap-2">
                    {equalizerBands.map((band, index) => (
                      <div key={band.frequency} className="flex flex-col items-center gap-2">
                        <input
                          type="range"
                          min="-12"
                          max="12"
                          step="0.1"
                          value={band.gain}
                          onChange={(e) => handleEqualizerChange(index, parseFloat(e.target.value))}
                          className="vertical-slider h-48 w-2 bg-gray-600 rounded-lg appearance-none cursor-pointer 
                      [&::-webkit-slider-thumb]:appearance-none [&::-webkit-slider-thumb]:w-4 [&::-webkit-slider-thumb]:h-4 
                      [&::-webkit-slider-thumb]:rounded-full [&::-webkit-slider-thumb]:bg-purple-500"
                        />
                        <span className="text-xs text-gray-400">{formatFrequency(band.frequency)}</span>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
            
            <audio
              ref={audioRef}
              src={audioUrl}
              onTimeUpdate={handleTimeUpdate}
              onPlay={() => setIsPlaying(true)}
              onPause={() => setIsPlaying(false)}
              onLoadedMetadata={handleTimeUpdate}
              autoPlay
              className="hidden"
            />
          </div>
        </div>
      )}
    </div>
  );
}

export default App;
