import { useEffect, useState, useMemo } from "react";
import { fetchProducts } from "../api";
import type { ProductRaw } from "../types";

const _ = (n: number): string => String.fromCharCode(n);
const TXT_TITLE = _(20840)+_(21697)+_(30446)+_(24405);
const TXT_SEARCH = _(25628)+_(32034)+_(21830)+_(21697)+_(21517)+_(31216)+_(8230);
const TXT_ALL_CAT = _(20840)+_(37096)+_(31867)+_(21035);
const TXT_LOADING = _(27491)+_(22312)+_(21152)+_(36733)+_(21830)+_(21697)+_(8230);
const TXT_ERROR = _(21152)+_(36733)+_(22833)+_(36133);
const TXT_RETRY = _(37325)+_(35797);
const TXT_NODATA = _(26410)+_(26524)+_(31526)+_(21305)+_(21830)+_(21697);
const TXT_STAR = _(35780)+_(20998);

export default function ProductBrowser() {
  const [products, setProducts] = useState<ProductRaw[]>([]);
  const [loading, setLoading] = useState<boolean>(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState<string>("");
  const [category, setCategory] = useState<string>("");
  const [selected, setSelected] = useState<ProductRaw | null>(null);

  const loadProducts = async (): Promise<void> => {
    setLoading(true); setError(null);
    try {
      const data = await fetchProducts();
      setProducts(data);
    } catch (err: unknown) {
      setError(err instanceof Error ? err.message : String(err));
    } finally { setLoading(false); }
  };
  useEffect(() => { loadProducts(); }, []);

  const categories = useMemo<string[]>(() => {
    const cats = new Set(products.map((p) => p.category));
    return Array.from(cats).sort();
  }, [products]);

  const filtered = useMemo<ProductRaw[]>(() => {
    return products.filter((p) => {
      const mc = !category || p.category === category;
      const ms = !search || p.title.toLowerCase().includes(search.toLowerCase());
      return mc && ms;
    });
  }, [products, category, search]);

  function starDisplay(rate: number): string {
    return String.fromCharCode(9733).repeat(Math.floor(rate)) + String.fromCharCode(9734).repeat(5 - Math.floor(rate));
  }

  return (
    <div className="product-browser">
      <div className="pb-header"><h2>{TXT_TITLE}</h2></div>
      <div className="pb-controls">
        <input className="pb-search" type="text" placeholder={TXT_SEARCH} value={search} onChange={(e) => setSearch(e.target.value)} />
        <select className="pb-cat-select" value={category} onChange={(e) => setCategory(e.target.value)}>
          <option value="">{TXT_ALL_CAT}</option>
          {categories.map((cat) => (<option key={cat} value={cat}>{cat}</option>))}
        </select>
      </div>
      {loading && (<div className="pb-loading"><div className="loading-spinner" /><span>{TXT_LOADING}</span></div>)}
      {error && (<div className="pb-error"><p>{TXT_ERROR}: {error}</p><button className="pb-retry-btn" onClick={loadProducts}>{TXT_RETRY}</button></div>)}
      {!loading && !error && filtered.length === 0 && (<div className="pb-empty"><p>{TXT_NODATA}</p></div>)}
      {!loading && !error && filtered.length > 0 && (
        <div className="pb-grid">
          {filtered.map((p) => (
            <div key={p.id} className="pb-card" onClick={() => setSelected(p)}>
              <div className="pb-card-img-wrap"><img className="pb-card-img" src={p.image} alt={p.title} loading="lazy" /></div>
              <div className="pb-card-body">
                <div className="pb-card-cat">{p.category}</div>
                <div className="pb-card-title">{p.title}</div>
                <div className="pb-card-footer">
                  <span className="pb-card-price">{String.fromCharCode(36)}{p.price.toFixed(2)}</span>
                  <span className="pb-card-rating">{TXT_STAR}: {p.rating.rate.toFixed(1)}</span>
                </div>
              </div>
            </div>
          ))}
        </div>
      )}
      {/* Modal */}
      {selected && (
        <div className="pb-modal-overlay" onClick={() => setSelected(null)}>
          <div className="pb-modal" onClick={(e) => e.stopPropagation()}>
            <button className="pb-modal-close" onClick={() => setSelected(null)}>&times;</button>
            <div className="pb-modal-content">
              <div className="pb-modal-img-wrap"><img className="pb-modal-img" src={selected.image} alt={selected.title} /></div>
              <div className="pb-modal-info">
                <div className="pb-modal-cat">{selected.category}</div>
                <h3 className="pb-modal-title">{selected.title}</h3>
                <div className="pb-modal-price">{String.fromCharCode(36)}{selected.price.toFixed(2)}</div>
                <div className="pb-modal-rating">
                  <span className="pb-stars">{starDisplay(selected.rating.rate)}</span>
                  <span className="pb-rating-text">{selected.rating.rate.toFixed(1)} / 5.0</span>
                  <span className="pb-review-count">(评论数: {selected.rating.count.toLocaleString()})</span>
                </div>
                <p className="pb-modal-desc">{selected.description}</p>
              </div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}