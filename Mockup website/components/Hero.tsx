import React from 'react';
import { IMAGES } from '../constants';

const Hero: React.FC = () => {
  return (
    <section 
      className="rounded-2xl overflow-hidden relative min-h-[500px] flex items-end md:items-center bg-cover bg-center group" 
      style={{
        backgroundImage: `linear-gradient(to right, rgba(0,0,0,0.7) 0%, rgba(0,0,0,0.3) 50%, rgba(0,0,0,0.1) 100%), url('${IMAGES.hero}')`
      }}
    >
      <div className="relative z-10 p-6 md:p-12 lg:p-16 w-full max-w-3xl flex flex-col items-start gap-6">
        <span className="inline-flex items-center rounded-full bg-primary/90 px-3 py-1 text-xs font-bold uppercase tracking-wide text-[#111814] backdrop-blur-sm">
          Directo del campo
        </span>
        <h1 className="text-4xl md:text-5xl lg:text-6xl font-black text-white leading-[1.1] tracking-tight drop-shadow-sm">
          Del Campo Colombiano <br className="hidden sm:block"/>a tu Mesa o Negocio
        </h1>
        <p className="text-white/90 text-base md:text-lg max-w-xl font-medium drop-shadow-md">
          Garantizamos frescura con recolección en menos de 24 horas. Precios justos para ti y para nuestros campesinos.
        </p>
        <div className="flex flex-col sm:flex-row gap-4 w-full sm:w-auto">
          <button className="bg-primary hover:bg-primary-hover text-[#111814] font-bold py-3.5 px-8 rounded-lg transition-transform active:scale-95 flex items-center justify-center gap-2 shadow-[0_0_20px_rgba(19,236,109,0.3)]">
            <span>Ver Catálogo</span>
            <span className="material-symbols-outlined text-[20px]">arrow_forward</span>
          </button>
        </div>
      </div>
    </section>
  );
};

export default Hero;