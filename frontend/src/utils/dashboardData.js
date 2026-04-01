function pad(value) {
  return String(value).padStart(2, '0')
}

export function toSlotString(date) {
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}T${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function normalizeDepartment(department) {
  if (!department) {
    return {
      did: null,
      name: '',
      description: null,
      doctors_registered: 0,
    }
  }

  return {
    did: department.did ?? null,
    name: department.name ?? '',
    description: department.description ?? null,
    doctors_registered: department.doctors_registered ?? 0,
  }
}

export function normalizeUser(user) {
  if (!user) return null

  const roleId = user.role_id ?? user.f_rid ?? null

  return {
    ...user,
    role_id: roleId,
    f_rid: roleId,
    blacklisted: Boolean(user.blacklisted),
    department: normalizeDepartment(user.department),
  }
}

export function formatLongDate(dateTime) {
  return new Date(dateTime).toLocaleDateString('en-US', {
    month: 'long',
    day: '2-digit',
    year: 'numeric',
  })
}

export function formatClockTime(dateTime) {
  return new Date(dateTime).toLocaleTimeString('en-US', {
    hour: '2-digit',
    minute: '2-digit',
    hour12: true,
  })
}

export function getAppointmentHistoryDateTime(appointment) {
  return appointment?.completed_at || appointment?.appointment_datetime || null
}

export function isAppointmentHistorical(appointment, now = new Date()) {
  const referenceDateTime = getAppointmentHistoryDateTime(appointment)
  if (!referenceDateTime) return false
  return appointment.status !== 'scheduled' || new Date(referenceDateTime) < now
}

export function normalizeAppointment(appointment) {
  if (!appointment) return null

  const patient = normalizeUser(appointment.patient)
  const doctor = normalizeUser(appointment.doctor)
  const historyDateTime = getAppointmentHistoryDateTime(appointment)

  return {
    ...appointment,
    patient,
    doctor,
    history_datetime: historyDateTime,
    patient_name: patient?.name ?? '',
    doctor_name: doctor?.name ?? '',
    formatted_time: formatClockTime(appointment.appointment_datetime),
    formatted_date: formatLongDate(appointment.appointment_datetime),
  }
}

export function buildDoctorCalendarData(appointments, availabilities, now = new Date()) {
  const availabilityMap = new Map(
    availabilities.map((item) => [item.slot_str, Boolean(item.available)]),
  )
  const scheduledAppointments = appointments
    .filter((appointment) => appointment.status === 'scheduled')
    .sort((left, right) => new Date(left.appointment_datetime) - new Date(right.appointment_datetime))

  const slotConfigs = [
    { hour: 9, minute: 0, label: '9AM - 11AM' },
    { hour: 12, minute: 0, label: '12PM - 2PM' },
    { hour: 15, minute: 0, label: '3PM - 5PM' },
    { hour: 18, minute: 0, label: '6PM - 8PM' },
  ]

  const calendarDays = []
  const daySlotsByDate = {}

  for (let offset = 0; offset < 8; offset += 1) {
    const currentDate = new Date(now.getFullYear(), now.getMonth(), now.getDate() + offset)
    const dateKey = toSlotString(currentDate).slice(0, 10)

    let formattedDate = currentDate.toLocaleDateString('en-US', {
      month: 'long',
      day: '2-digit',
    })
    if (offset === 0) formattedDate = 'Today'
    if (offset === 1) formattedDate = 'Tomorrow'

    const appointmentCount = scheduledAppointments.filter(
      (appointment) => appointment.appointment_datetime.slice(0, 10) === dateKey,
    ).length

    calendarDays.push({
      date: dateKey,
      formatted_date: formattedDate,
      appointment_count: appointmentCount,
    })

    daySlotsByDate[dateKey] = slotConfigs.map((config) => {
      const slotDate = new Date(
        currentDate.getFullYear(),
        currentDate.getMonth(),
        currentDate.getDate(),
        config.hour,
        config.minute,
      )
      const slotStr = toSlotString(slotDate)
      const bookedAppointment = scheduledAppointments.find(
        (appointment) => appointment.appointment_datetime.slice(0, 16) === slotStr,
      )

      if (bookedAppointment) {
        return {
          slot_str: slotStr,
          time_range: config.label,
          booked: true,
          patient_name: bookedAppointment.patient?.name ?? bookedAppointment.patient_name ?? '',
          appointment_id: bookedAppointment.aid,
        }
      }

      const isPast = slotDate < now
      const storedAvailable = availabilityMap.has(slotStr) ? availabilityMap.get(slotStr) : true
      const available = storedAvailable && !isPast

      return {
        slot_str: slotStr,
        time_range: config.label,
        booked: false,
        available,
        status: available ? 'available' : 'unavailable',
        is_past: isPast,
      }
    })
  }

  return {
    calendarDays,
    daySlotsByDate,
    allAppointments: scheduledAppointments,
  }
}
