import React from 'react';
import { IMAGES } from '../constants';

const Footer: React.FC = () => {
  return (
    <footer className="bg-white dark:bg-[#1a2e22] border-t border-[#f0f4f2] dark:border-[#2a4032] pt-16 pb-8">
      <div className="max-w-[1440px] mx-auto px-4 md:px-10">
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-4 gap-10 mb-12">
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 text-text-main dark:text-white">
              <div className="h-8 w-auto">
                <img 
                  alt="Comercializadora Guapante Logo" 
                  className="h-full w-auto object-contain" 
                  src={IMAGES.footerLogo} 
                />
              </div>
              <h2 className="text-lg font-black tracking-tight">Guapante</h2>
            </div>
            <p className="text-text-muted text-sm">
              Llevamos lo mejor del campo colombiano a tu hogar o negocio con transparencia, frescura y sostenibilidad.
            </p>
            <div className="flex gap-4 mt-2">
              <a className="text-text-muted hover:text-primary transition-colors flex items-center" href="#"><span className="material-symbols-outlined">thumb_up</span></a>
              <a className="text-text-muted hover:text-primary transition-colors flex items-center" href="#"><span className="material-symbols-outlined">photo_camera</span></a>
            </div>
          </div>

          <div className="hidden md:block">
            <h3 className="font-bold text-text-main dark:text-white mb-4">Comprar</h3>
            <ul className="flex flex-col gap-2 text-sm text-text-muted">
              <li><a className="hover:text-primary transition-colors" href="#">Todas las Categorías</a></li>
              <li><a className="hover:text-primary transition-colors" href="#">Ofertas Semanales</a></li>
              <li><a className="hover:text-primary transition-colors" href="#">Nuevos Productos</a></li>
              <li><a className="hover:text-primary transition-colors" href="#">Zona Mayorista</a></li>
            </ul>
          </div>

          <div className="hidden md:block">
            <h3 className="font-bold text-text-main dark:text-white mb-4">Compañía</h3>
            <ul className="flex flex-col gap-2 text-sm text-text-muted">
              <li><a className="hover:text-primary transition-colors" href="#">Sobre Nosotros</a></li>
              <li><a className="hover:text-primary transition-colors" href="#">Nuestros Agricultores</a></li>
              <li><a className="hover:text-primary transition-colors" href="#">Sostenibilidad</a></li>
              <li><a className="hover:text-primary transition-colors" href="#">Trabaja con Nosotros</a></li>
            </ul>
          </div>

          <div className="hidden md:block">
            <h3 className="font-bold text-text-main dark:text-white mb-4">Ayuda</h3>
            <ul className="flex flex-col gap-2 text-sm text-text-muted">
              <li><a className="hover:text-primary transition-colors" href="#">Centro de Ayuda</a></li>
              <li><a className="hover:text-primary transition-colors" href="#">Envíos y Devoluciones</a></li>
              <li><a className="hover:text-primary transition-colors" href="#">Política de Privacidad</a></li>
              <li><a className="hover:text-primary transition-colors" href="#">Contacto</a></li>
            </ul>
          </div>

          {/* Mobile Accordions */}
          <div className="md:hidden flex flex-col gap-6">
            <details className="group border-b border-[#f0f4f2] dark:border-[#2a4032] pb-4">
              <summary className="flex justify-between items-center font-bold text-text-main dark:text-white cursor-pointer list-none">
                Comprar
                <span className="material-symbols-outlined transition-transform duration-200 group-open:rotate-180">expand_more</span>
              </summary>
              <ul className="flex flex-col gap-3 text-sm text-text-muted mt-4 pl-1">
                <li><a className="hover:text-primary transition-colors" href="#">Todas las Categorías</a></li>
                <li><a className="hover:text-primary transition-colors" href="#">Ofertas Semanales</a></li>
                <li><a className="hover:text-primary transition-colors" href="#">Nuevos Productos</a></li>
                <li><a className="hover:text-primary transition-colors" href="#">Zona Mayorista</a></li>
              </ul>
            </details>

            <details className="group border-b border-[#f0f4f2] dark:border-[#2a4032] pb-4">
              <summary className="flex justify-between items-center font-bold text-text-main dark:text-white cursor-pointer list-none">
                Compañía
                <span className="material-symbols-outlined transition-transform duration-200 group-open:rotate-180">expand_more</span>
              </summary>
              <ul className="flex flex-col gap-3 text-sm text-text-muted mt-4 pl-1">
                <li><a className="hover:text-primary transition-colors" href="#">Sobre Nosotros</a></li>
                <li><a className="hover:text-primary transition-colors" href="#">Nuestros Agricultores</a></li>
                <li><a className="hover:text-primary transition-colors" href="#">Sostenibilidad</a></li>
                <li><a className="hover:text-primary transition-colors" href="#">Trabaja con Nosotros</a></li>
              </ul>
            </details>

            <details className="group border-b border-[#f0f4f2] dark:border-[#2a4032] pb-4">
              <summary className="flex justify-between items-center font-bold text-text-main dark:text-white cursor-pointer list-none">
                Ayuda
                <span className="material-symbols-outlined transition-transform duration-200 group-open:rotate-180">expand_more</span>
              </summary>
              <ul className="flex flex-col gap-3 text-sm text-text-muted mt-4 pl-1">
                <li><a className="hover:text-primary transition-colors" href="#">Centro de Ayuda</a></li>
                <li><a className="hover:text-primary transition-colors" href="#">Envíos y Devoluciones</a></li>
                <li><a className="hover:text-primary transition-colors" href="#">Política de Privacidad</a></li>
                <li><a className="hover:text-primary transition-colors" href="#">Contacto</a></li>
              </ul>
            </details>
          </div>
        </div>

        <div className="border-t border-[#f0f4f2] dark:border-[#2a4032] pt-8 flex flex-col md:flex-row justify-between items-center gap-4 text-xs text-text-muted">
          <p>© 2024 Comercializadora Guapante S.A.S. Todos los derechos reservados.</p>
          <div className="flex items-center gap-6">
            <span>Hecho con <span className="text-primary">❤</span> en Colombia</span>
          </div>
        </div>
      </div>
    </footer>
  );
};

export default Footer;