import { Category, Feature, Product } from "./types";

export const IMAGES = {
  logo: "https://lh3.googleusercontent.com/aida-public/AB6AXuAJXtlsP92oDL8zoeLr1Q7X8K-brDeWr1kpdevgZSm4XW1fy_fHC3PLTIV6zkZrB2w-JNBL9wa4L4obYBaNJYpT5AzzORXSUZzslB5dlM08lmPYzUhaUbhrLCxgJtMWRZjbv8SZmPuYjD_HP8KLL--43ttB1NIWdD077PWoPhjUyOCzMU5YXXzwAVQ1KRK6LV_H5wb8GB4bEmRJVwDxDw-fyZpxgFmgHX3kzf7_RCO7Wf-jYvMW_dSy9sw7s9JN-nQr_wTVw9xF6TI",
  hero: "https://lh3.googleusercontent.com/aida-public/AB6AXuA73TR9wUARZpltEl6KrrKxJNYLGdNyNkX1tEhxJ92CWvL300TPA4AbLms-u06ZEy_UgWQWgaTY5JXv8ptUsuTdEQSmrHgQi_asQT_d3H-sTNu0kQXDHRTxm_Fq1GFX6l1EzeyOrWsWNCmnOdHL9pd_yEQIn2cbWaLYB54jIPluit4uYARYdGHNFe2HBHkiIOXAoXJuX-8ouMlmlUFSSFqOc1LuMbLM-bmDQNuZaEu5wD_XVLSgH0z_LVq3mWXMIgeOYkDC1mNeAaA",
  businessBg: "https://lh3.googleusercontent.com/aida-public/AB6AXuCtmW4Ydq8GzzpGhXDg3dfxsB8J4EuM_Fif9rPx19J0-SATwaceaeUVqvHY6JOqvTfB1Ifh_RuDO_eYEjniQdijXY88qhpimqpI7dxoKx7LQCog-cdmgyCPcfGUI3sLEDyU8DaJhvSvlBUNLIPjt8GLVaHqy2KkJAv8OdgYsvwr7y4somWUmzIiDf_cns58PXkmiQuIEhJAG5dApPBiv4clPDL2HU5UorvPl4GaB1QYnft2yjypnvHad8v7arkXZiyJoF4zgOowh6o",
  footerLogo: "https://lh3.googleusercontent.com/aida-public/AB6AXuCwwhQN1nVymFNYZP8SFjAAIaoORC4hgWkKtgrZgBavP1RrqJZfjZ9P4_CmvtDAyHeXjdnzirtUGDfPRY0Pj2ibZgAvoRYEDHvhcPd6ndD79DEfsyu-zN9Frmaw-oP6BTySVhb_fXF474sDfBIJxE9KDpiQoQef_D4kkjn-wf0Eb6cbhizNly3q5Iyzyzw9QhU2LrUMYfuxxGf_L-MUodUHteoIUSs3Oe6aKWabA2laLqVh4sOZhHQMnoYGjgvpuCdlzH6EjZIBwHE"
};

export const CATEGORIES: Category[] = [
  {
    id: 'frutas',
    name: 'Frutas',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuC1e6VygCw9NxCj2d95i8GalqIOGmailzGOgHtLsKCGANJt_ErzSlDKsCZULc99O6PFwiMlYBQS2GEW4mMWGGcJJrheUp6MzmDDQaJ5f0fj-RylqhopZjH83DZqLAFd9mg5ilp_OCpNtyZkq2Q6S_Ehd2ul3yIXqI8lFkw_Kqq50LWL1KsN_poBcM1GvvGjtDIWITb98Ci4qoo44TEFm40XcWJ_4Sv6PxfMZKcQgQTO48cClIdIQVUIG7TGhvbTOs5VFPIHEi3SW9Y',
    bgColorClass: 'bg-orange-50 dark:bg-orange-900/20'
  },
  {
    id: 'verduras',
    name: 'Verduras',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDGnDMRXriQD3LuyTHpoud1XJJKjmvvYftGdisc1Uf_YpT71MNjm37-43y2zZmpB5aOv9BS6bt0DBE4XAY0Z7kp0r8PPk96Pwe4TFQicZb5ZQWFGVswrhMXmi2w6vTnA4ok-eivDPivgWCiLBGM30k2aJljA55ff6fEokLjLWLhDvXVxYvsfYZQ7Jfk8ozK2N6P2XoEdnKNjdlb6udzky3k9KftAx6zPW_jrVxxnq9yi9mvL7Ov0KiAedtr-kLyJ08wYBtyI2HaE80',
    bgColorClass: 'bg-green-50 dark:bg-green-900/20'
  },
  {
    id: 'tuberculos',
    name: 'Tubérculos',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCWbg9X2X-K3GpmkiPyPSDlj8jpk93wFMs0Xk7_oB3K0a7paZw4a3cEOg1zeq6s-hSm4nbdsOTIckKlyfAwOJlNCEz7owzf6rf7xSh92-kPT5IOawZY_h98ordt-enbHalfDMHL5Y-6fIOtBqojXVROimDlyBYrzwg9AqJDQvrI69Q9WJ5Jhr3CGWzpdg9hL4TCerNHHtoZXxWY3m-_TzJE47gRIT0lGJ9D7XtPuHIemea-J0bXP6iMM8hiQ_Kzb92elJ6e8zfEo9k',
    bgColorClass: 'bg-yellow-50 dark:bg-yellow-900/20'
  },
  {
    id: 'organicos',
    name: 'Orgánicos',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBB_ULA5cbocxYEJmf2axcqN4dqZCsPhEm9VWQpWFMAgoGzm3Ju8yQncbmXNUSlHzP-EuSYQJICakQ_JsBu4EYb9vSsp3D3mJfapYBAPmlaIigSL1gEphWQ60-WOCHg4INdzgbd3cOTZRqSMp9tkrfntW1KNWTLUTK3S1mgFnpfSe-v4Nu1T0e86SmD_ijDrMV5wOwDPCOnJ7ehRlHM3I_9onohi6kWaWysw5mK1-DSDuPsklXbNWIbUcApUScawUy2Rs70ZOLbzkQ',
    bgColorClass: 'bg-red-50 dark:bg-red-900/20'
  },
  {
    id: 'hierbas',
    name: 'Hierbas',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuBzKavoK0uMkcX2GQvP_vEvRpHd1Y_FOa38XCc2a0UP4NgLbFSDmkV6ddzNa19qJbtEfrH6Nnv7U9IW1mlpiX1Q3HIIvMoj0PEbQ0z7y8mco-5EiDxuHERSMMiEx__FcrpViIDmIzQTDmnjTqTFpnR8ctfb0iuoR6HVd4jCUF5G9EkiowfY7A_OhnoW87V0DF4bdN-ROOp54bSt17Osl_1jsVI33RzEq2PDb7PmfHS5iJ6SzFHjHMTiwwlPCumg6eRgmz4xDbJlkTg',
    bgColorClass: 'bg-purple-50 dark:bg-purple-900/20'
  },
  {
    id: 'granos',
    name: 'Granos',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuDnrYvKFmdD6Aav7okMXN2r_Pv4kbF5rUvWWrWVfyw4JwNsCsnoUhvLM9zdZb1PnlPd7OK6oWziQHMHnpBcNKdUg4XL38_0fq9T97thTl8qugGuvtQXgKAwtePiCQjENyR8eme1wZiVYptPzhgiKcn2Uz8E_zSTctn-Ta7WE3lUFmdp181MFuGq2Ka0XocHDZ4-FvafMJWfUUaQh9Jq2e1JMPH5KkXx5jEcP2M5YjjRr13vJpH5yiLm0ua1ZT8L4SGF6UiJO1NYUlw',
    bgColorClass: 'bg-stone-50 dark:bg-stone-900/20'
  }
];

export const PRODUCTS: Product[] = [
  {
    id: 'aguacate',
    name: 'Aguacate Hass',
    origin: 'Antioquia',
    discount: '-15%',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuA3LAoC5RVjfPdPrDbRHVplRJhzdfvjyaXdSESRWqy3wGAcqtJHO7KUHsTqPjQBf1RvcmKRd8T8a8nPGR8qgvRhXOxljDUY1Hp487U7Sw1N9pXjoUb1hwsLmnAGu6fyCkNzfd_Q0AYB_z6o1vpJyuOtpjqjJCMzzsRLkEKJq-tJz48AAKQ6v3TchD1Z8j7wJ4-zFeJkqs_1tMcMkd10X-g_ptN3SubvtJ-Fw5smSocPCWqEcN8_bKMH98pk1aELYINKx50mKB3ra1c'
  },
  {
    id: 'banano',
    name: 'Banano Criollo',
    origin: 'Urabá',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuC9uH7YCpnzGw168GsYtnT3vKiKDOPU3f-6Z7Z8lHndyhTo8qECIPSIEP9Rkr7sok5DGAkifpZRYw5rR-Wwak3Atr7iQ2m3X2NEdqOI1BUGPEQ457GWvfXdi8vAinYPNHXMQbJ5E5-Dpn3PE0x6Ovd9jzK2KzQf6RokZ3UAc_HY6ySp00P3HvCnM2K4oVunh7RDo5APV04CnqPZVqozqnOhsSTLCRWzq3HfImDO2ScG8jKa6NaZYjpH0czAg83t4hlMu108kSH1dAU'
  },
  {
    id: 'tomate',
    name: 'Tomate Chonto',
    origin: 'Cundinamarca',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuC996VNQm0nmMeZqDr1xLxpq2gXicvzSx-0vkZyUtWGtsF5SrYPjpQFe0O4vzFK3nLOwjjXxTc1f-bKPoEDINuA7WX-4TZq-lA4iy2zTnCj62MPOPmb27JprBmxpLvqOKOXh6QLmo7359dFaLF4kQ91tKYnuUZ8T_zqSQOLMYkRZ6wiCXLmmVlAaWx9l93rR0fqa6PGmD_71P1Xiwx7jrwQqqWavAgWfw_VPzOzuU3kb_fQV3L-M--nemLjF8H12b1sB6k2l_yYD7Q'
  },
  {
    id: 'papa',
    name: 'Papa Capira',
    origin: 'Boyacá',
    image: 'https://lh3.googleusercontent.com/aida-public/AB6AXuCZD4_fKZcTZrNifjfENLPiRvD9li9sOfU4xNs1ChmNBzQVBGV8zokIrqxu8rLLRCBuO1hRxPtD3GI3Us-6cBzKv_-7umWZ5oCO3PduayW7cGYP5S5OdRH7DX26T8O7I49VnY5AmOUQwuypy4LLIN2fucddAY0GgyI7NlnrJS4opIGRUrPDasLVScErpJSZ82NIORle-t4Xq_5XHyGCkDyKW_9k-xza7nAdEes_2Y-CQR5MxtrgYVPCXXByMO3B8UL1iyVdkLzn8Zs'
  }
];

export const FEATURES: Feature[] = [
  {
    icon: 'schedule',
    title: 'Frescura 24h',
    description: 'Nuestros productos son recolectados y entregados en tiempo récord para garantizar su sabor.',
    iconBgClass: 'bg-green-50 dark:bg-green-900/30',
    iconColorClass: 'text-green-600 dark:text-green-400'
  },
  {
    icon: 'local_shipping',
    title: 'Logística Superior',
    description: 'Flota propia refrigerada que asegura la cadena de frío hasta la puerta de tu casa o local.',
    iconBgClass: 'bg-blue-50 dark:bg-blue-900/30',
    iconColorClass: 'text-blue-600 dark:text-blue-400'
  },
  {
    icon: 'handshake',
    title: 'Comercio Justo',
    description: 'Trabajamos directamente con familias campesinas, eliminando intermediarios innecesarios.',
    iconBgClass: 'bg-orange-50 dark:bg-orange-900/30',
    iconColorClass: 'text-orange-600 dark:text-orange-400'
  }
];