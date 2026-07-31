/** Typed clients for household, nutrition-data, substitution, and research APIs. */
const configuredBase=import.meta.env.VITE_API_BASE_URL as string|undefined;
const API_BASE=(configuredBase?.trim()||(import.meta.env.DEV?"http://localhost:8000/api/v1":"/api/v1")).replace(/\/$/,"");
const TOKEN_KEY="nutriflavor_token";
async function request<T>(path:string,options:RequestInit={}):Promise<T>{
  const headers=new Headers(options.headers); if(!(options.body instanceof FormData)&&!headers.has("Content-Type")) headers.set("Content-Type","application/json"); const token=localStorage.getItem(TOKEN_KEY); if(token) headers.set("Authorization",`Bearer ${token}`); const response=await fetch(`${API_BASE}${path}`,{...options,headers}); const contentType=response.headers.get("content-type")||""; const payload:unknown=contentType.includes("application/json")?await response.json():await response.text(); if(!response.ok){const detail=payload&&typeof payload==="object"&&"detail" in payload?(payload as {detail:unknown}).detail:payload; const message=typeof detail==="string"?detail:detail&&typeof detail==="object"&&"message" in detail?String((detail as {message:unknown}).message):`Request failed: ${response.status}`; throw new Error(message)} return payload as T;
}
export interface QuantityRange{quantity_min:number;quantity_max:number;unit:string}
export interface Household{id:string;owner_user_id:string;name:string;timezone:string;version:number;created_at:string;updated_at:string}
export interface HouseholdMember{id:number;household_id:string;display_name:string;linked_user_id?:string|null;servings_multiplier:number;allergies:string[];dietary_restrictions:string[];disliked_ingredients:string[];active:boolean;created_at:string}
export interface PantryItem{id:number;household_id:string;canonical_name:string;display_name:string;quantity_min:number;quantity_max:number;unit:string;expires_at?:string|null;opened_at?:string|null;source:string;metadata:Record<string,unknown>;version:number;created_at:string;updated_at:string}
export interface Leftover{id:number;household_id:string;recipe_id:string;source_plan_id?:number|null;portions_available:number;cooked_at:string;expires_at?:string|null;frozen:boolean;notes?:string|null;version:number;created_at:string;updated_at:string}
export interface InventoryEvent{id:number;household_id:string;pantry_item_id?:number|null;leftover_id?:number|null;event_type:string;quantity_min:number;quantity_max:number;unit:string;reason?:string|null;metadata:Record<string,unknown>;idempotency_key?:string|null;created_at:string}
export interface ReconciledShoppingItem{canonical_name:string;display_name:string;unit:string;required_min:number;required_max:number;pantry_min:number;pantry_max:number;buy_min:number;buy_max:number;coverage_status:string;expiring_quantity_max:number;source_recipe_ids:string[];notes:string[]}
export interface BatchPrepTask{recipe_id:string;recipe_name:string;total_portions:number;first_day:number;scheduled_day:number;occurrences:number;meal_slots:string[];storage_guidance_status:string}
export interface SubstitutionCandidate{ingredient:string;replacement:string;role:string;ratio?:number|null;score:number;reasons:string[];warnings:string[]}
export interface ResearchCatalogSummary{[collection:string]:Record<string,number>}
export const householdApi={
  create:(name:string,timezone="UTC")=>request<Household>("/households",{method:"POST",body:JSON.stringify({name,timezone})}),
  list:()=>request<Household[]>("/households"),
  get:(id:string)=>request<{household:Household;members:HouseholdMember[];active_servings_multiplier:number;planning_status:string}>(`/households/${encodeURIComponent(id)}`),
  addMember:(id:string,payload:Record<string,unknown>)=>request<HouseholdMember>(`/households/${encodeURIComponent(id)}/members`,{method:"POST",body:JSON.stringify(payload)}),
  pantry:(id:string,includeEmpty=false)=>request<PantryItem[]>(`/households/${encodeURIComponent(id)}/pantry?include_empty=${includeEmpty}`),
  addPantry:(id:string,payload:Record<string,unknown>)=>request<PantryItem>(`/households/${encodeURIComponent(id)}/pantry`,{method:"POST",body:JSON.stringify(payload)}),
  consumePantry:(id:string,itemId:number,payload:Record<string,unknown>)=>request<PantryItem>(`/households/${encodeURIComponent(id)}/pantry/${itemId}/consume`,{method:"POST",body:JSON.stringify(payload)}),
  adjustPantry:(id:string,itemId:number,payload:Record<string,unknown>)=>request<PantryItem>(`/households/${encodeURIComponent(id)}/pantry/${itemId}`,{method:"PUT",body:JSON.stringify(payload)}),
  events:(id:string)=>request<InventoryEvent[]>(`/households/${encodeURIComponent(id)}/inventory-events`),
  leftovers:(id:string)=>request<Leftover[]>(`/households/${encodeURIComponent(id)}/leftovers`),
  addLeftover:(id:string,payload:Record<string,unknown>)=>request<Leftover>(`/households/${encodeURIComponent(id)}/leftovers`,{method:"POST",body:JSON.stringify(payload)}),
  consumeLeftover:(id:string,leftoverId:number,payload:Record<string,unknown>)=>request<Leftover>(`/households/${encodeURIComponent(id)}/leftovers/${leftoverId}/consume`,{method:"POST",body:JSON.stringify(payload)}),
  reconcileShopping:(id:string)=>request<ReconciledShoppingItem[]>(`/households/${encodeURIComponent(id)}/shopping-reconciliation`),
  batchPrep:(id:string)=>request<BatchPrepTask[]>(`/households/${encodeURIComponent(id)}/batch-prep`),
};
export const substitutionApi={suggest:(payload:Record<string,unknown>)=>request<SubstitutionCandidate[]>("/substitutions/suggest",{method:"POST",body:JSON.stringify(payload)})};
export const nutritionDataApi={search:(q:string,pageSize=25)=>request<Record<string,unknown>>(`/nutrition-data/search?q=${encodeURIComponent(q)}&page_size=${pageSize}`),food:(fdcId:number)=>request<Record<string,unknown>>(`/nutrition-data/foods/${fdcId}`)};
export const researchApi={catalog:()=>request<{catalog:Record<string,unknown>;summary:ResearchCatalogSummary}>("/research/catalog"),collection:(name:string,readiness?:string)=>request<Record<string,unknown>>(`/research/${encodeURIComponent(name)}${readiness?`?readiness=${encodeURIComponent(readiness)}`:""}`),datasetCard:(id:string,version="unversioned")=>request<Record<string,unknown>>(`/research/cards/datasets/${encodeURIComponent(id)}?version=${encodeURIComponent(version)}`),modelCard:(id:string,version="unversioned")=>request<Record<string,unknown>>(`/research/cards/models/${encodeURIComponent(id)}?version=${encodeURIComponent(version)}`),validateRun:(config:Record<string,unknown>)=>request<Record<string,unknown>>("/research/validate-run-config",{method:"POST",body:JSON.stringify(config)}),numericDrift:(payload:Record<string,unknown>)=>request<Record<string,unknown>>("/research/drift/numeric",{method:"POST",body:JSON.stringify(payload)})};
