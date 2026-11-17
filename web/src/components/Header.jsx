import React, { useState, useEffect } from 'react';
import { Satellite, Info, Radio, Layers, Clock, Globe } from 'lucide-react';

export default function Header({ 
  channels = [],
  currentChannel,
  onSelectChannel,
  channelMeta, 
  coords, 
  currentFrame, 
  apiOnline, 
  onOpenInfo,
  onToggleSidebar,
  sidebarOpen
}) {
  const [utcTime, setUtcTime] = useState('');

  // Live UTC Clock
  useEffect(() => {
    const updateTime = () => {
      const now = new Date();
      setUtcTime(now.toUTCString().replace('GMT', 'UTC'));
    };
    updateTime();
    const timer = setInterval(updateTime, 1000);
    return () => clearInterval(timer);
  }, []);

  return (
    <header className="h-14 bg-slate-900/95 border-b border-slate-800/80 px-4 flex items-center justify-between z-30 shadow-md backdrop-blur-sm">
      {/* Left: Branding & Direct Channel Dropdown */}
      <div className="flex items-center space-x-3">
        <button
          onClick={onToggleSidebar}
          className={`p-2 rounded-lg transition-colors ${
            sidebarOpen ? 'bg-sky-600/30 text-sky-400 border border-sky-500/40' : 'bg-slate-800 text-slate-300 hover:bg-slate-700'
          }`}
          title="Alternar panel de capas y opacidad"
        >
          <Layers className="w-4 h-4" />
        </button>

        <div className="flex items-center space-x-2.5">
          <div className="p-1.5 bg-gradient-to-tr from-sky-600 to-indigo-600 rounded-lg shadow-inner">
            <Satellite className="w-5 h-5 text-white" />
          </div>
          <div className="flex flex-col">
            <div className="flex items-center space-x-2">
              <span className="font-bold text-xs sm:text-sm tracking-wide text-white uppercase">GOES Sat-Viewer</span>
              <span className="text-[10px] px-1.5 py-0.2 rounded bg-sky-950 text-sky-300 border border-sky-800/60 font-mono">
                ABI
              </span>
            </div>
            
            {/* Direct Channel Selector Dropdown */}
            <div className="relative mt-0.5">
              <select
                value={currentChannel}
                onChange={(e) => onSelectChannel(e.target.value)}
                className="bg-slate-800 hover:bg-slate-750 text-sky-300 border border-slate-700 rounded px-2 py-0.5 text-xs font-semibold focus:outline-none focus:ring-1 focus:ring-sky-500 cursor-pointer max-w-[210px] sm:max-w-[280px] truncate"
                title="Seleccionar canal espectral ABI"
              >
                <optgroup label="Visible & Near-IR (Reflectancia)">
                  {channels.filter(c => ['C01','C02','C03','C04','C05','C06'].includes(c.channel)).map(c => (
                    <option key={c.channel} value={c.channel}>
                      {c.channel} - {c.name} ({c.wavelength_um} µm)
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Vapor de Agua Troposférico">
                  {channels.filter(c => ['C08','C09','C10'].includes(c.channel)).map(c => (
                    <option key={c.channel} value={c.channel}>
                      {c.channel} - {c.name} ({c.wavelength_um} µm)
                    </option>
                  ))}
                </optgroup>
                <optgroup label="Infrarrojo Térmico & Ventana">
                  {channels.filter(c => ['C07','C11','C12','C13','C14','C15','C16'].includes(c.channel)).map(c => (
                    <option key={c.channel} value={c.channel}>
                      {c.channel} - {c.name} ({c.wavelength_um} µm)
                    </option>
                  ))}
                </optgroup>
              </select>
            </div>
          </div>
        </div>
      </div>

      {/* Center: Live Frame UTC Timestamp */}
      <div className="hidden md:flex items-center space-x-4 bg-slate-950/70 border border-slate-800/80 px-3.5 py-1 rounded-full text-xs font-mono">
        <div className="flex items-center space-x-1.5 text-slate-400">
          <Clock className="w-3.5 h-3.5 text-sky-400" />
          <span>Cuadro Satelital:</span>
        </div>
        <span className="font-semibold text-sky-300 tracking-wider">
          {currentFrame?.iso_utc ? currentFrame.iso_utc.replace('T', ' ').replace(':00Z', 'Z') : 'Sin cuadro cargado'}
        </span>
      </div>

      {/* Right: Lat/Lon coordinates, API status & Info button */}
      <div className="flex items-center space-x-3">
        {/* Lat/Lon Cursor Readout */}
        <div className="hidden lg:flex items-center space-x-2 bg-slate-950/60 border border-slate-800/80 px-3 py-1 rounded-md text-xs font-mono text-slate-300">
          <Globe className="w-3.5 h-3.5 text-slate-400" />
          <span>
            {coords.lat !== null && coords.lon !== null
              ? `${coords.lat.toFixed(3)}°N, ${coords.lon.toFixed(3)}°W`
              : 'Mover cursor en mapa'}
          </span>
        </div>

        {/* API Status Pill */}
        <div 
          className={`flex items-center space-x-1.5 px-2.5 py-1 rounded-full text-[11px] font-medium border ${
            apiOnline 
              ? 'bg-emerald-950/40 text-emerald-300 border-emerald-800/50' 
              : 'bg-rose-950/40 text-rose-300 border-rose-800/50'
          }`}
          title={apiOnline ? 'Conexión con Backend REST API activa' : 'Backend API no responde'}
        >
          <span className={`w-2 h-2 rounded-full ${apiOnline ? 'bg-emerald-400 animate-pulse' : 'bg-rose-500'}`} />
          <span className="hidden sm:inline">{apiOnline ? 'API Conectado' : 'API Desconectado'}</span>
        </div>

        {/* Academic / Info Modal Trigger */}
        <button
          onClick={onOpenInfo}
          className="p-1.5 rounded-lg bg-slate-800 hover:bg-slate-700 text-slate-300 hover:text-white transition-colors"
          title="Información Científica y Arquitectura"
        >
          <Info className="w-4 h-4" />
        </button>
      </div>
    </header>
  );
}
