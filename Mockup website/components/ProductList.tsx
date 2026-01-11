import React from 'react';
import { PRODUCTS } from '../constants';

const ProductList: React.FC = () => {
  return (
    <section>
      <div className="flex items-center gap-3 mb-6">
        <h2 className="text-2xl font-bold tracking-tight text-text-main dark:text-white">Cosecha en temporada</h2>
        <span className="bg-primary/20 text-[#111814] text-xs font-bold px-2 py-1 rounded-md dark:text-white dark:bg-primary/40">Ofertas Flash</span>
      </div>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-6">
        {PRODUCTS.map((product) => (
          <div key={product.id} className="group bg-white dark:bg-[#1a2e22] rounded-xl border border-[#f0f4f2] dark:border-[#2a4032] overflow-hidden hover:shadow-lg transition-all flex flex-col">
            <div className="relative h-48 overflow-hidden bg-gray-100 dark:bg-gray-800">
              <img 
                alt={product.name} 
                className="w-full h-full object-cover group-hover:scale-105 transition-transform duration-500" 
                src={product.image} 
              />
              <button className="absolute top-3 right-3 p-2 bg-white/80 dark:bg-black/50 backdrop-blur rounded-full text-gray-500 hover:text-red-500 transition-colors flex items-center justify-center">
                <span className="material-symbols-outlined text-[20px]">favorite</span>
              </button>
              {product.discount && (
                <div className="absolute bottom-3 left-3 bg-primary text-[#111814] text-xs font-bold px-2 py-1 rounded">
                  {product.discount}
                </div>
              )}
            </div>
            <div className="p-4 flex flex-col gap-2 flex-1">
              <div className="flex-1">
                <h3 className="font-bold text-lg text-text-main dark:text-white group-hover:text-primary transition-colors">{product.name}</h3>
                <p className="text-xs text-text-muted">Origen: {product.origin}</p>
              </div>
              <div className="flex items-end justify-end mt-2">
                <button className="size-10 rounded-lg bg-[#f0f4f2] dark:bg-[#25382c] hover:bg-primary hover:text-[#111814] text-text-main dark:text-white flex items-center justify-center transition-colors">
                  <span className="material-symbols-outlined">add</span>
                </button>
              </div>
            </div>
          </div>
        ))}
      </div>
    </section>
  );
};

export default ProductList;