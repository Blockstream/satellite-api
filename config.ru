# To launch: bundle exec rackup

require 'rubygems'
require 'bundler'

Bundler.require

require './main'
run Sinatra::Application
