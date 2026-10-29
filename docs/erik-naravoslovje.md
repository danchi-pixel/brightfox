# Erikovo naravoslovje

Source: all 38 supplied photographs from `erik narav`, reviewed individually. The content is paraphrased and source-referenced; original photographs remain outside Git.

## Open locally

Run `start.bat`, open Erik’s classroom, then choose **Erikovo naravoslovje**. The canonical topic is assigned only to Erik in family `danijel`. Local-family visibility is automatic; production still requires approval of the current version. Restart the backend after installing this code so additive migration `0004` runs.

If setting up another PC, copy the original photographs privately and run:

```powershell
backend\.venv\Scripts\python.exe scripts\import-study-images.py "C:\Users\User\Desktop\erik narav"
```

The importer touches no database. Files go in `data/files/study/danijel/2026-10-28-erik-naravoslovje/`; the existing file backup includes them. Production deployment excludes `data`, so these private assets need a separate authenticated server transfer before publishing. Do not commit textbook pages or learner worksheets.

## Coverage

13 lessons; 99 questions (77 oral, 22 checked); 11 picture exercises; 67 flashcards. Picture exercises overlap other counts.

| Topic | Sources | Oral | Quiz | Pictures | Cards |
|---|---|---:|---:|---:|---:|
| Snovi okoli nas | p38, p32 | 4 | 2 | 0 | 4 |
| Majhni delci, velike razlike | p37, p36, p32, p31 | 4 | 2 | 1 | 4 |
| Od surovine do predmeta | p36, p35, p34, p31 | 6 | 2 | 0 | 6 |
| Znaki, ki nas varujejo | p33, p32, p31 | 4 | 1 | 1 | 3 |
| Od Sonca do Zemlje | p11, p14, p30 | 6 | 2 | 1 | 5 |
| Sledi davnega življenja | p12, p13, p14 | 4 | 2 | 1 | 3 |
| Kamninski detektivi | p29, p28, p27, p26, p25, p23, p31 | 10 | 2 | 1 | 9 |
| Življenje pod nogami | p25, p24, p23 | 6 | 1 | 1 | 5 |
| Organizmi in njihovo okolje | p09, p02, p03 | 4 | 1 | 1 | 3 |
| Vreme pod povečevalom | p04, p05, p06, p07, p08, p10 | 8 | 2 | 1 | 7 |
| Sonce in drugi viri energije | p21, p20, p22 | 6 | 2 | 0 | 6 |
| Tokovi in elektrarne | p19, p18, p17, p15 | 9 | 1 | 2 | 7 |
| Kam potuje toplota? | p16, p01, p15 | 6 | 2 | 1 | 5 |

The in-app **Viri in opombe** view expands every source photo and lists its related question IDs. Mock oral sessions mix topics and include a picture prompt where available; the 5–10 question setting applies across the bank. Topic filtering applies to the other modes.

## Source register and review notes

| ID | Source | Review note |
|---|---|---|
| p01 | Delovni list: toplotni tok | Ročne meritve v tabeli niso dovolj jasne za preverjanje številčnih odgovorov. Vadimo smer prenosa toplote. |
| p02 | List: rastline v visokogorju | — |
| p03 | Zapiski in fotografiji gorskih rastlin | — |
| p04 | Delovni list: padavine | — |
| p05 | Delovni list: veter | — |
| p06 | Delovni list: vlažnost zraka | — |
| p07 | Delovni list: zračni tlak | — |
| p08 | Delovni list: temperatura | Desni rob višinskega diagrama je odrezan. Ne preverjamo odrezanih temperatur. |
| p09 | Delovni list: ekosistem – akvarij | — |
| p10 | Delovni list: neživi dejavniki in termometri | Tabela ima neskladni enoti za padavine in osvetljenost. Za padavine uporabimo mm oziroma L/m² iz lista o padavinah; osvetljenost vadimo z merilnikom, brez sporne enote. Odčitka termometrov nista dovolj jasna. |
| p11 | Utrjevanje: vesolje in pogoji za življenje | — |
| p12 | Utrjevanje: fosili in časovni trak | Časovni trak in list o razvoju življenja uporabljata različne datume za človeka. Vadimo zaporedje, ne enega točnega datuma. |
| p13 | Delovni list: prepoznavanje fosilov | Zgornja ilustracija ob amonitu je podobna današnjemu glavonožcu. Naloga prepoznavanja uporablja fotografijo fosila pod njo. |
| p14 | Delovni list: razvoj življenja | List ponovi več kot 90 % izumrtja pri dveh različnih dogodkih in vsebuje napačen ročni vpis pri 66 milijonih let. Ti deleži niso uporabljeni. Starost Zemlje je v gradivu zaokrožena na 4,5 oziroma 4,6 milijarde let. |
| p15 | Učbenik, str. 52–53: energija – ponovitev | — |
| p16 | Učbenik, str. 50–51: toplotni tok | — |
| p17 | Učbenik, str. 48–49: električni tok in energija | — |
| p18 | Učbenik, str. 46–47: elektrika in vodni tok | — |
| p19 | Učbenik, str. 44–45: elektrarne | Časovno odvisne deleže proizvodnje elektrike v Sloveniji iz starega učbenika izpustimo. |
| p20 | Učbenik, str. 42–43: viri energije | — |
| p21 | Učbenik, str. 40–41: sončna energija | — |
| p22 | Učbenik: uvod v energijo | — |
| p23 | Učbenik, str. 36–37: kamnine in prst – ponovitev | — |
| p24 | Učbenik, str. 34–35: vrste prsti | — |
| p25 | Učbenik, str. 32–33: določanje kamnin in nastanek prsti | — |
| p26 | Učbenik, str. 30–31: geološka karta in trdota | — |
| p27 | Učbenik, str. 28–29: sedimentne in metamorfne kamnine | — |
| p28 | Učbenik, str. 26–27: magmatske in sedimentne kamnine | — |
| p29 | Učbenik, str. 24–25: kamninski krog | — |
| p30 | Učbenik, str. 22–23: Zemlja in vulkani | Risba označi ozračje do 50 km; tega ne obravnavamo kot zgornjo mejo celotnega ozračja. |
| p31 | Učbenik, str. 20 in uvod v kamnine | — |
| p32 | Učbenik, str. 18–19: varnost in ponovitev snovi | Navodila za prvo pomoč niso vključena v učne odgovore; ta del naj z otrokom obravnava odrasla oseba. Vadimo prepoznavanje nevarnosti in obvestilo odrasli osebi. |
| p33 | Učbenik, str. 16–17: znaki za nevarnost | — |
| p34 | Učbenik, str. 14–15: fosilna goriva | — |
| p35 | Učbenik, str. 12–13: apno, malta, beton, steklo | Shema stekla navaja samo nad 100 °C, kar ni uporabna temperatura za izdelavo stekla. Vprašanja preverjajo surovine in zaporedje, ne temperature. |
| p36 | Učbenik, str. 10–11: delci in viri surovin | — |
| p37 | Učbenik, str. 8–9: delci in agregatna stanja | — |
| p38 | Učbenik, str. 6–7: lastnosti in uporaba snovi | — |

## Persistence and limits

Self-assessment supports known / practising / not yet. Flashcards prioritise weak recall, with known cards due in 1, 2, 4… days (maximum 30). Saved sessions resume after refresh. No streaks, microphone, AI calls or school-grade claims. Optional typed oral answers stay only in the current exercise. Readiness and existing practice runs remain separate. Parents have a read-only preview.

No production deployment has been performed. Browser QA uses disposable scratch accounts and a loopback-only server, not household accounts.

## Verification (29 October 2026)

- Backend: 75 tests pass, including route tenancy, private images, progress conflicts and spacing.
- Frontend: 45 tests pass; TypeScript and the Vite production build pass.
- Content checker passes; all 38 source files are present in local private storage.
- Browser: desktop (1280px) and mobile (390px), oral hints and typed draft, answer reveal,
  self-assessment saved across refresh, a complete mixed-topic mock and its summary,
  fill-in answer and five-part picture labeling checked. All 11 image crops visually reviewed
  and corrected; no missing picture responses observed.
