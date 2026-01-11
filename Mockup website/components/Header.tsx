import React from 'react';
import { IMAGES } from '../constants';

const Header: React.FC = () => {
  return (
    <header className="sticky top-0 z-50 w-full bg-white dark:bg-[#1a2e22] border-b border-[#f0f4f2] dark:border-[#2a4032] shadow-sm">
      <div className="px-4 md:px-10 py-3 flex items-center justify-between gap-4 max-w-[1440px] mx-auto">
        <div className="flex items-center gap-3 text-text-main dark:text-white shrink-0">
          <div className="h-10 w-auto">
            <img 
              alt="Comercializadora Guapante Logo" 
              className="h-full w-auto object-contain" 
              src={IMAGES.logo} 
            />
          </div>
          <h2 className="text-lg md:text-xl font-black tracking-tight hidden sm:block">Guapante</h2>
        </div>

        <nav className="hidden lg:flex items-center gap-6 xl:gap-9">
          <a className="text-sm font-medium hover:text-primary transition-colors" href="#">Categorías</a>
          <a className="text-sm font-medium hover:text-primary transition-colors" href="#">Ofertas</a>
          <a className="text-sm font-medium hover:text-primary transition-colors" href="#">Nosotros</a>
          <a className="text-sm font-medium hover:text-primary transition-colors" href="#">Logística</a>
        </nav>

        <div className="flex-1 max-w-lg mx-4 hidden md:block">
          <div className="relative flex w-full items-center h-10 rounded-lg bg-[#f0f4f2] dark:bg-[#25382c] overflow-hidden focus-within:ring-2 ring-primary/50 transition-all">
            <div className="pl-4 pr-2 text-text-muted">
              <span className="material-symbols-outlined text-[20px]">search</span>
            </div>
            <input 
              className="w-full bg-transparent border-none text-sm text-text-main dark:text-white placeholder-text-muted focus:ring-0 focus:outline-none h-full" 
              placeholder="Buscar frutas, verduras..." 
            />
          </div>
        </div>

        <div className="flex items-center gap-3 shrink-0">
          <button className="md:hidden flex items-center justify-center size-10 rounded-full hover:bg-[#f0f4f2] dark:hover:bg-[#25382c]">
            <span className="material-symbols-outlined">search</span>
          </button>
          <button className="hidden sm:flex items-center gap-2 px-3 h-10 rounded-lg hover:bg-[#f0f4f2] dark:hover:bg-[#25382c] transition-colors text-text-main dark:text-white">
            <span className="material-symbols-outlined">account_circle</span>
            <span className="text-sm font-bold hidden xl:inline">Mi Cuenta</span>
          </button>
          <button className="flex items-center justify-center gap-2 px-3 h-10 rounded-lg bg-primary/10 text-primary hover:bg-primary hover:text-[#111814] transition-all group relative">
            <span className="material-symbols-outlined group-hover:text-[#111814]">shopping_basket</span>
            <span className="font-bold text-sm hidden sm:inline group-hover:text-[#111814]">$0</span>
            <span className="absolute -top-1 -right-1 flex size-4 items-center justify-center rounded-full bg-red-500 text-[10px] font-bold text-white">0</span>
          </button>
        </div>
      </div>

      <div className="lg:hidden flex justify-between px-6 py-2 border-t border-[#f0f4f2] dark:border-[#2a4032] overflow-x-auto whitespace-nowrap gap-6 no-scrollbar">
        <a className="text-sm font-medium text-primary" href="#">Inicio</a>
        <a className="text-sm font-medium text-text-muted hover:text-primary" href="#">Categorías</a>
        <a className="text-sm font-medium text-text-muted hover:text-primary" href="#">Ofertas</a>
        <a className="text-sm font-medium text-text-muted hover:text-primary" href="#">B2B</a>
      </div>
    </header>
  );
};

export default Header;