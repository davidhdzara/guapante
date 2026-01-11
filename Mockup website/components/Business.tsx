import React from 'react';
import { IMAGES } from '../constants';

const Business: React.FC = () => {
  return (
    <section className="relative rounded-2xl overflow-hidden bg-[#1a2e22] text-white p-8 md:p-12 flex flex-col md:flex-row items-center justify-between gap-8">
      <div className="absolute inset-0 z-0">
        <img 
          alt="Background pattern of vegetables" 
          className="w-full h-full object-cover opacity-20 mix-blend-overlay" 
          src={IMAGES.businessBg} 
        />
      </div>
      <div className="relative z-10 flex-1 max-w-lg">
        <h2 className="text-3xl font-black mb-4">¿Tienes un restaurante o tienda?</h2>
        <p className="text-white/80 mb-6 font-medium">Accede a precios mayoristas exclusivos, programación de entregas recurrentes y soporte prioritario.</p>
        <button className="bg-primary text-[#111814] font-bold py-3 px-6 rounded-lg hover:bg-primary-hover transition-colors">
          Crear Cuenta de Negocio
        </button>
      </div>
      <div className="relative z-10 hidden md:block w-1/3">
        <div className="bg-white/10 backdrop-blur-md p-6 rounded-xl border border-white/20">
          <div className="flex items-center gap-4 mb-4">
            <div className="size-10 rounded-full bg-primary flex items-center justify-center text-[#111814] font-bold shrink-0">1</div>
            <span className="font-medium">Regístrate como empresa</span>
          </div>
          <div className="flex items-center gap-4 mb-4">
            <div className="size-10 rounded-full bg-primary flex items-center justify-center text-[#111814] font-bold shrink-0">2</div>
            <span className="font-medium">Selecciona tus productos</span>
          </div>
          <div className="flex items-center gap-4">
            <div className="size-10 rounded-full bg-primary flex items-center justify-center text-[#111814] font-bold shrink-0">3</div>
            <span className="font-medium">Recibe con factura</span>
          </div>
        </div>
      </div>
    </section>
  );
};

export default Business;