require "sinatra/activerecord"
require_relative '../constants'
require_relative './orders'
require_relative './regions'

class Region < ActiveRecord::Base
  validates :number, presence: true
  has_many :tx_confirmations
  has_many :rx_confirmations
  
  enum number: [:north_america, :south_america, :africa, :europe, :asia]
  
  REGIONS = {}
    
  seed_regions = [
    {number: 0, satellite_name: 'Galaxy 18', coverage: 'North America', has_receiver: true},
    {number: 1, satellite_name: 'Eutelsat 113', coverage: 'South America', has_receiver: false},
    {number: 2, satellite_name: 'Telstar 11N', coverage: 'Africa', has_receiver: false},
    {number: 3, satellite_name: 'Telstar 11N', coverage: 'Europe', has_receiver: false},
    {number: 4, satellite_name: 'Telstar 18V', coverage: 'Asia', has_receiver: true},
  ]
  seed_regions.each do |region_hash|
    region = Region.find_or_initialize_by(number: region_hash[:number])
    region.update(region_hash)
  end

  Region.numbers.each do |sym, num|
    sym = sym.to_sym
    REGIONS[sym] = Region.find_by_number(sym)
  end

end
