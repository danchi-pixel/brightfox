// @vitest-environment jsdom
import { cleanup, fireEvent, render, screen } from "@testing-library/react";
import { afterEach, describe, expect, it, vi } from "vitest";
import { Exercise } from "./Exercise";
import { activeQuestions, isCorrect, makeSession, resumable, shuffle, sourceGroup } from "./session";
import type { Bank, Progress, Question } from "./types";

const q: Question = { id: "a", topic: "one", kind: "oral", prompt: "Razloži pojav.", answer: "Vzorčni odgovor.", points: ["Prva točka"], hints: ["Namig.", "Močnejši namig."], sources: ["p01"], difficulty: 1, card: true, followup: "Zakaj?", followup_answer: "Razlaga dodatnega vprašanja." };
const bank: Bank = { title: "Učna zbirka", lessons: [{id:"one",title:"Tema",summary:"",icon:"",notes:[],vocabulary:{},sources:["p01"]}], questions: [q], sources: [{id:"p01",file:"a.jpg",group:"notebook",label:"Vir",width:1200,height:1600,rotate:0,review:""}], review_notes:[] };
const empty: Progress = { revision:0, answers:{}, session:null };
afterEach(cleanup);
const click = (name: string) => fireEvent.click(screen.getByRole("button",{name}));

describe("Oral practice", () => {
  it("hides answers until an attempt, supports typed draft, hints, follow-up and self-assessment", () => {
    const rate = vi.fn();
    render(<Exercise question={q} bank={bank} base="/scratch" mode="oral" busy={false} onRate={rate} />);
    expect(screen.queryByText(q.answer)).toBeNull();
    expect(screen.queryByRole("button",{name:"Pokaži pravilen odgovor"})).toBeNull();
    fireEvent.click(screen.getByText("Raje zapišem odgovor"));
    fireEvent.change(screen.getByLabelText("Moj odgovor"), {target:{value:"Moj poskus"}});
    click("Pokaži namig 1"); expect(screen.getByText("Namig.")).toBeTruthy();
    click("Moj odgovor je končan"); click("Pokaži pravilen odgovor");
    expect(screen.getByText(q.answer)).toBeTruthy();
    fireEvent.click(screen.getByText("Dodatno vprašanje: Zakaj?"));
    click("Pokaži razlago dodatnega vprašanja"); expect(screen.getByText(q.followup_answer!)).toBeTruthy();
    click("Še vadim"); expect(rate).toHaveBeenCalledWith("practice");
  });
  it("flips a card in one action", () => {
    render(<Exercise question={q} bank={bank} base="/scratch" mode="cards" busy={false} onRate={vi.fn()} />);
    click("Obrni kartico"); expect(screen.getByText(q.answer)).toBeTruthy();
  });
  it("explains a wrong quiz choice without hiding the answer", () => {
    const rate = vi.fn();
    render(<Exercise question={{...q,kind:"choice",options:["Da","Ne"],correct:["Da"]}} bank={bank} base="/scratch" mode="quiz" busy={false} onRate={rate} />);
    fireEvent.click(screen.getByLabelText("Ne")); click("Preveri odgovor");
    expect(screen.getByText(q.answer)).toBeTruthy(); click("Naslednje vprašanje"); expect(rate).toHaveBeenCalledWith("practice");
  });
  it("keeps retryable answer and disables submission while saving", () => {
    const rate = vi.fn();
    const {rerender} = render(<Exercise question={q} bank={bank} base="/scratch" mode="oral" busy={false} onRate={rate} />);
    click("Moj odgovor je končan"); click("Pokaži pravilen odgovor");
    rerender(<Exercise question={q} bank={bank} base="/scratch" mode="oral" busy onRate={rate} />);
    click("Znam"); expect(rate).not.toHaveBeenCalled(); expect(screen.getByText(q.answer)).toBeTruthy();
  });
});
describe("Session selection and answers", () => {
  it("excludes textbook and ambiguous sources from every mode until parent activation", () => {
    const b: Bank = {...bank, sources:[...bank.sources,{...bank.sources[0],id:"p02",group:"textbook"}], questions: []};
    b.questions = [q,{...q,id:"book",sources:["p02"]},{...q,id:"mixed",sources:["p01","p02"]},{...q,id:"unknown",sources:["missing"]}].flatMap(x => [x,{...x,id:x.id+"-quiz",kind:"choice" as const,options:["Yes"],correct:["Yes"],image:{source:x.sources[0],box:[0,0,100,100],alt:"Slika"}}]);
    const before=JSON.stringify(b);
    for (const mode of ["oral","mock","quiz","cards","images"] as const) {
      expect(makeSession(b,mode,empty).queue.every(id => id === "a" || id === "a-quiz")).toBe(true);
      expect(makeSession(b,mode,empty,"all",10,false,["one"]).queue.some(id => id.startsWith("book"))).toBe(true);
    }
    expect(activeQuestions(b,["one"]).some(x=>x.id.startsWith("mixed")||x.id.startsWith("unknown"))).toBe(false);
    expect(sourceGroup(b,[])).toBe("review");
    expect(JSON.stringify(b)).toBe(before);
  });
  it("resumes only active questions without altering stored sessions or answer history", () => {
    const session={mode:"oral" as const,queue:["book","a","mixed","b"],index:2,ratings:{book:"know" as const,a:"practice" as const}};
    const before=JSON.stringify(session);
    expect(resumable(session,new Set(["a","b"]))).toEqual({...session,queue:["a","b"],index:1,ratings:{a:"practice"}});
    expect(resumable(session,new Set(["a"]))).toBeNull();
    expect(JSON.stringify(session)).toBe(before);
  });
  it("mixes mock topics without duplicates and includes a visual prompt", () => {
    const questions = Array.from({length:30},(_,i) => ({...q,id:String(i),topic:String(i%10),...(i===29?{image:{source:"p01",box:[0,0,100,100] as [number,number,number,number],alt:"Slika"}}:{})}));
    const session=makeSession({...bank,questions},"mock",empty,"one",7);
    expect(session.queue.length).toBe(7); expect(new Set(session.queue).size).toBe(7);
    expect(new Set(session.queue.map(id=>questions.find(x=>x.id===id)!.topic)).size).toBe(7);
    expect(session.queue).toContain("29");
  });
  it("prioritizes weaker cards and keeps card recall separate", () => {
    const b={...bank,questions:[q,{...q,id:"b"}]};
    const p={...empty,answers:{"cards:b":{rating:"again" as const,attempts:1,due:new Date().toISOString(),interval:0,updated:""}}};
    expect(makeSession(b,"cards",p).queue[0]).toBe("b");
    expect(makeSession(b,"oral",p,"all",7,true).queue).toEqual([]);
  });
  it("checks classification, ordering and fill answers", () => {
    expect(isCorrect({...q,kind:"fill",correct:["para"]},[" PARA. "])).toBe(true);
    expect(isCorrect({...q,kind:"sequence",correct:["a","b"]},["b","a"])).toBe(false);
    expect(isCorrect({...q,kind:"match",correct:["a","b"]},["a","b"])).toBe(true);
    const original=[1,2,3]; expect(shuffle(original,()=>0)).not.toEqual(original); expect(original).toEqual([1,2,3]);
  });
});
