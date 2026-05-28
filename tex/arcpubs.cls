\NeedsTeXFormat{LaTeX2e}[1994/06/01]
\ProvidesPackage{arcpubs}[2026/05/26 Publication list class]

\LoadClass[a4paper,12pt]{article}

\usepackage{textcomp}
\usepackage[T1]{fontenc}
\usepackage[utf8]{inputenc}
\usepackage[normalem]{ulem}
\usepackage{sectsty}
\RequirePackage[margin=0.5cm]{geometry}
\RequirePackage[
  backend=biber,
  url=false,
  doi=false,
  isbn=false,
  style=phys,
  biblabel=brackets,
  sorting=ydnt,
  texencoding=utf8,
  defernumbers=true
]{biblatex}

\DeclareNameFormat{author}{%
\ifthenelse{\equal{\namepartfamily}{\filterlastname}}%
    {\textbf{\uline{\ifblank{\namepartgiveni}{}{\namepartgiveni\space}\namepartfamily}}}%
    {\ifblank{\namepartgiveni}{}{\namepartgiveni\space}\namepartfamily}%
\ifthenelse{\value{listcount}<\value{liststop}}%
    {\addcomma\space}
    {}}

\DeclareBibliographyCategory{byname}
\DeclareIndexNameFormat{byname}{%
  \ifboolexpr{ test {\ifdefstring{\filterlastname}{#1}}}
    {\addtocategory{byname}{\thefield{entrykey}}}
    {}}

\defbibcheck{recent}{}
\newcommand{\StartYear}[1]{%
\defbibcheck{recent}{%
\ifboolexpr{ not test {\iffieldint{year}} or test {\ifnumless{\thefield{year}}{#1}}}
{\skipentry}
{}%
}}

\newcommand{\Author}[1]{\newcommand{\filterlastname}{#1}}

\DeclareBibliographyCategory{relevant}
\AtEveryBibitem{%
  \ifcategory{relevant}%
    {* }%
    {}%
}

\renewbibmacro{in:}{}
\AtEveryBibitem{\clearlist{language}}
\AtEveryBibitem{\clearfield{eprintclass}}
\AtDataInput{\indexnames[byname][1-99]{author}}

\renewcommand*{\bibfont}{\raggedright}

\newcommand{\showbooks}{\printbibliography[title={Books}, type=book, check=recent]}
\newcommand{\showchapters}{\printbibliography[title={Book Chapters}, type=inbook, check=recent, heading=subbibliography]}
\newcommand{\showarticles}{\printbibliography[title={Journal Articles}, type=article, notkeyword=preprint, check=recent, heading=subbibliography]}
\newcommand{\showproceedings}{\printbibliography[title={Conference Proceedings}, type=inproceedings, check=recent, heading=subbibliography]}
\newcommand{\showpreprints}{\printbibliography[title={Pre-prints}, keyword=preprint, check=recent, heading=subbibliography]}

\sectionfont{\fontsize{12}{15}\bfseries\selectfont}
\subsectionfont{\fontsize{12}{15}\selectfont}
\pagestyle{empty}

\endinput
