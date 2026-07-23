import { Mail, Phone, MapPin, User, Globe, Contact } from 'lucide-react'

export interface ContactCardProps {
  name?: string
  email?: string
  phone?: string
  address?: string
  linkedin?: string
  github?: string
  portfolio?: string
}

export function ContactCard({
  name = 'Not Available',
  email = 'Not Available',
  phone = 'Not Available',
  address = 'Not Available',
  linkedin = 'Not Available',
  github = 'Not Available',
  portfolio = 'Not Available'
}: ContactCardProps) {
  const fields = [
    { label: 'Candidate Name', val: name, icon: <User className="h-4 w-4 text-indigo-600" /> },
    { label: 'Email Address', val: email, icon: <Mail className="h-4 w-4 text-sky-600" /> },
    { label: 'Phone Number', val: phone, icon: <Phone className="h-4 w-4 text-emerald-600" /> },
    { label: 'Contact Location', val: address, icon: <MapPin className="h-4 w-4 text-rose-600" /> },
    {
      label: 'LinkedIn Profile',
      val: linkedin,
      icon: (
        <svg className="h-4 w-4 text-blue-600 fill-current" viewBox="0 0 24 24">
          <path d="M19 3a2 2 0 0 1 2 2v14a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h14m-.5 15.5v-5.3a3.26 3.26 0 0 0-3.26-3.26c-.85 0-1.84.52-2.28 1.3v-1.11h-2.79v8.37h2.79v-4.93c0-.77.62-1.4 1.39-1.4a1.4 1.4 0 0 1 1.4 1.4v4.93h2.75M6.46 10.9v8.37H9.25V10.9H6.46M7.86 6.7a1.6 1.6 0 1 0 0 3.2 1.6 1.6 0 0 0 0-3.2z" />
        </svg>
      )
    },
    {
      label: 'GitHub Repository',
      val: github,
      icon: (
        <svg className="h-4 w-4 text-slate-800 fill-current" viewBox="0 0 24 24">
          <path d="M12 2A10 10 0 0 0 2 12c0 4.42 2.87 8.17 6.84 9.5.5.08.66-.23.66-.5v-1.69c-2.77.6-3.36-1.34-3.36-1.34-.46-1.16-1.11-1.47-1.11-1.47-.91-.62.07-.6.07-.6 1 .07 1.53 1.03 1.53 1.03.87 1.52 2.34 1.07 2.91.83.1-.65.35-1.09.63-1.34-2.22-.25-4.55-1.11-4.55-4.92 0-1.11.38-2 1.03-2.71-.1-.25-.45-1.29.1-2.64 0 0 .84-.27 2.75 1.02.79-.22 1.65-.33 2.5-.33.85 0 1.71.11 2.5.33 1.91-1.29 2.75-1.02 2.75-1.02.55 1.35.2 2.39.1 2.64.65.71 1.03 1.6 1.03 2.71 0 3.82-2.34 4.66-4.57 4.91.36.31.69.92.69 1.85V21c0 .27.16.59.67.5C19.14 20.16 22 16.42 22 12A10 10 0 0 0 12 2z" />
        </svg>
      )
    },
    { label: 'Personal Portfolio', val: portfolio, icon: <Globe className="h-4 w-4 text-purple-600" /> },
  ]

  return (
    <div className="flex flex-col gap-3.5 p-4.5 bg-white border border-slate-200 rounded-2xl shadow-sm my-1">
      <div className="flex items-center gap-2 font-black text-slate-900 text-xs uppercase tracking-wider border-b border-slate-200 pb-2.5">
        <Contact className="h-4 w-4 text-indigo-600" />
        <span>Candidate Information & Contact Grid</span>
      </div>

      <div className="grid grid-cols-1 md:grid-cols-2 gap-2.5 text-xs pt-0.5">
        {fields.map((f, idx) => {
          const isAvail = f.val && f.val !== 'Not Available'
          return (
            <div key={idx} className="flex items-center gap-3 p-3 bg-slate-50 border border-slate-200 rounded-xl hover:bg-white transition-all">
              <div className="h-9 w-9 rounded-xl bg-white border border-slate-200 flex items-center justify-center shrink-0 shadow-2xs">
                {f.icon}
              </div>
              <div className="overflow-hidden">
                <div className="text-[10px] uppercase font-black text-slate-600 tracking-wider">{f.label}</div>
                <div className={`font-extrabold truncate mt-0.5 ${isAvail ? 'text-slate-900 select-all' : 'text-slate-500 italic font-semibold text-[11px]'}`}>
                  {f.val}
                </div>
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
